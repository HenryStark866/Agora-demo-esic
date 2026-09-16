# -*- coding: utf-8 -*-
"""
orquestador.py — Escenario 1: chatbot con RAG gobernado

Pipeline (ver Documento 1, sección 4.1):
  1 seguridad de entrada   5 datos en vivo vía function calling
  2 router de intención    6 generación con grounding
  3 caché semántica        7 verificación de groundedness
  4 recuperación híbrida   8 traza y telemetría

La decisión de diseño que define este archivo: el sistema PREFIERE NO RESPONDER
antes que responder sin evidencia. En una institución educativa, una respuesta
inventada sobre requisitos o financiación es un problema legal, no un bug.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from comun.llm_gateway import LLMGateway, Tarea, PresupuestoExcedido
from escenario1_chatbot import prompts

log = logging.getLogger("fabrica.e1")

UMBRAL_GROUNDEDNESS   = 0.70
UMBRAL_CONFIANZA_RUTA = 0.60
TOP_K                 = 8
TOP_N_RERANK          = 4
MAX_VUELTAS_TOOLS     = 3

# Valores cerrados. Todo lo que el modelo devuelve se valida contra estas listas
# antes de usarse: la salida de un LLM es entrada no confiable.
AUDIENCIAS_VALIDAS = {"aspirante", "estudiante", "egresado", "empresa", "desconocido"}
# Frase canónica que el prompt RESPUESTA ordena usar cuando no hay evidencia.
FRASE_SIN_EVIDENCIA = "No tengo esa información confirmada"
RUTA_SEGURA = {"intencion": "desconocida", "audiencia": "desconocido",
               "requiere_dato_vivo": False, "complejidad": "simple",
               "requiere_humano": True, "en_dominio": True, "confianza": 0.0}


@dataclass
class Contexto:
    conv_id: str
    canal: str                      # web | whatsapp | teams | email
    audiencia: str = "desconocido"
    usuario_id: str | None = None   # None = sesión anónima, sin PII
    autenticado: bool = False


@dataclass
class Resultado:
    texto: str
    fuentes: list[dict]
    derivar_a_humano: bool = False
    motivo_derivacion: str | None = None
    paquete_handoff: dict | None = None
    groundedness: float | None = None
    costo_usd: float = 0.0          # costo TOTAL del turno (router + generación + verificación)
    latencia_ms: int = 0
    traza: list[dict] | None = None  # pasos ejecutados, para observabilidad y demo


# ===========================================================================
# HERRAMIENTAS — datos vivos. Nunca se indexan (ADR-04).
# Todas son de SOLO LECTURA. El modelo no puede escribir en sistemas de ESIC.
# ===========================================================================
TOOLS = [
    {"type": "function", "function": {
        "name": "consultar_precio_vigente",
        "description": ("Precio, formas de pago y descuentos vigentes de un programa. "
                        "ÚSALA SIEMPRE que el usuario pregunte por costos. "
                        "Jamás respondas un precio sin llamar esta función."),
        "parameters": {"type": "object", "properties": {
            "codigo_programa": {"type": "string"},
            "cohorte": {"type": "string", "description": "AAAA-S, ej. 2026-2"}},
            "required": ["codigo_programa"]}}},
    {"type": "function", "function": {
        "name": "consultar_fechas_admision",
        "description": "Fechas de cierre de inscripción, inicio de clases y cupos disponibles.",
        "parameters": {"type": "object", "properties": {
            "codigo_programa": {"type": "string"}}, "required": ["codigo_programa"]}}},
    {"type": "function", "function": {
        "name": "consultar_estado_solicitud",
        "description": ("Estado de la solicitud de admisión del usuario. "
                        "Requiere sesión autenticada."),
        "parameters": {"type": "object", "properties": {
            "documento": {"type": "string"}}, "required": ["documento"]}}},
    {"type": "function", "function": {
        "name": "buscar_vacantes_egresados",
        "description": "Vacantes activas en la bolsa de empleo de egresados de ESIC.",
        "parameters": {"type": "object", "properties": {
            "area": {"type": "string"},
            "ciudad": {"type": "string"},
            "limite": {"type": "integer", "default": 5}}, "required": ["area"]}}},
]

TOOLS_QUE_EXIGEN_AUTH = {"consultar_estado_solicitud"}
NOMBRES_TOOLS = {t["function"]["name"] for t in TOOLS}


def _json_o_none(texto: str | None):
    """Parsea JSON tolerando cercas de código markdown; None si no es JSON."""
    t = (texto or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("\n") + 1:] if "\n" in t else t
    try:
        return json.loads(t)
    except (json.JSONDecodeError, TypeError):
        return None


def _bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true"
    raise ValueError(f"no es booleano: {v!r}")


class Orquestador:
    def __init__(self, llm: LLMGateway, buscador, herramientas, safety, cache_sem):
        self.llm, self.buscador = llm, buscador
        self.herramientas = herramientas      # implementaciones reales de TOOLS
        self.safety = safety                  # Azure AI Content Safety + Prompt Shields
        self.cache_sem = cache_sem

    # ------------------------------------------------------------------ main
    def responder(self, mensaje: str, ctx: Contexto, historial: list[dict]) -> Resultado:
        t0 = time.perf_counter()
        gasto0 = self.llm.gasto(ctx.conv_id)
        self._traza: list[dict] = []
        try:
            res = self._pipeline(mensaje, ctx, historial)
        except PresupuestoExcedido as e:
            log.warning("presupuesto agotado: %s", e)
            res = self._derivar(mensaje, ctx, historial,
                                "presupuesto de conversación agotado", resumir=False)
        except Exception:  # noqa: BLE001
            log.exception("fallo en pipeline conv=%s", ctx.conv_id)
            # Degradación elegante: nunca un stacktrace al usuario, y la promesa
            # de "te conecto con un asesor" se cumple creando el caso.
            res = self._derivar(mensaje, ctx, historial, "error técnico",
                                resumir=False)
        res.costo_usd = round(self.llm.gasto(ctx.conv_id) - gasto0, 6)
        res.latencia_ms = int((time.perf_counter() - t0) * 1000)
        res.traza = self._traza
        return res

    def _paso(self, n: int, nombre: str, **datos) -> None:
        self._traza.append({"paso": n, "nombre": nombre, **datos})

    # -------------------------------------------------------------- pipeline
    def _pipeline(self, mensaje: str, ctx: Contexto, historial: list[dict]) -> Resultado:

        # [1] Seguridad de entrada -------------------------------------------
        veredicto = self.safety.analizar_entrada(mensaje)
        self._paso(1, "seguridad de entrada",
                   resultado="bloqueado" if veredicto.bloqueado else "limpio")
        if veredicto.bloqueado:
            return Resultado(
                texto=("No puedo ayudarte con eso. Puedo resolverte dudas sobre "
                       "programas, admisiones, financiación y servicios de ESIC."),
                fuentes=[])

        # [2] Router de intención --------------------------------------------
        ruta = self._rutear(mensaje, ctx, historial)
        self._paso(2, "router de intención", **ruta)
        log.info("ruta", extra={"conv": ctx.conv_id,
                                "ruta": json.dumps(ruta, ensure_ascii=False)})

        if not ruta["en_dominio"]:
            return Resultado(
                texto=("Solo puedo ayudarte con temas de ESIC Medellín. "
                       "Por ejemplo: requisitos de admisión de un máster, "
                       "opciones de financiación o servicios para egresados. "
                       "¿Te sirve alguno de esos?"),
                fuentes=[])

        if ruta["requiere_humano"] or ruta["confianza"] < UMBRAL_CONFIANZA_RUTA:
            motivo = ("solicitud explícita o caso delicado" if ruta["requiere_humano"]
                      else f"confianza de clasificación baja ({ruta['confianza']:.2f})")
            return self._derivar(mensaje, ctx, historial, motivo,
                                 humano_pedido=ruta["requiere_humano"])

        if ruta["audiencia"] != "desconocido":
            ctx.audiencia = ruta["audiencia"]

        # [3] Caché semántica -------------------------------------------------
        # Solo para consultas sin dato vivo: un precio cacheado es un precio viejo.
        if ruta["requiere_dato_vivo"]:
            self._paso(3, "caché semántica", resultado="omitida (hay dato vivo)")
        else:
            hit = self.cache_sem.buscar(mensaje, ctx.audiencia)
            self._paso(3, "caché semántica",
                       resultado="acierto" if hit else "sin acierto",
                       similitud=(hit or {}).get("similitud"))
            if hit:
                return Resultado(texto=hit["texto"], fuentes=hit["fuentes"],
                                 groundedness=hit.get("groundedness"))

        # [4] Recuperación híbrida -------------------------------------------
        fragmentos = self._recuperar(mensaje, ctx)
        self._paso(4, "recuperación híbrida", audiencia=ctx.audiencia,
                   fragmentos=[{"id": f"F{i+1}", "titulo": f["titulo"],
                                "score": f.get("score")}
                               for i, f in enumerate(fragmentos)])
        if not fragmentos and not ruta["requiere_dato_vivo"]:
            self._registrar_vacio(mensaje, ctx)   # alimenta el backlog de contenido
            return self._derivar(mensaje, ctx, historial,
                                 "sin evidencia en la base de conocimiento")

        # [5][6] Generación con herramientas ---------------------------------
        tarea = Tarea.RAZONAMIENTO if ruta["complejidad"] == "compleja" else Tarea.RESPUESTA
        texto, datos_vivos, completo = self._generar(
            mensaje, ctx, historial, fragmentos, tarea)
        self._paso(5, "datos en vivo (function calling)",
                   llamadas=[{"herramienta": d["herramienta"], "args": d["args"],
                              "salida": d["salida"]} for d in datos_vivos])
        self._paso(6, "generación con grounding",
                   modelo=self.llm.ruteo[tarea]["modelo"], texto=texto)
        if not completo:
            return self._derivar(mensaje, ctx, historial,
                                 "límite de llamadas a herramientas")
        if FRASE_SIN_EVIDENCIA.lower() in texto.lower():
            # El modelo reconoce que no tiene el dato: se cumple la promesa de
            # conectar con un asesor y el hueco queda registrado.
            self._registrar_vacio(mensaje, ctx)
            return self._derivar(mensaje, ctx, historial,
                                 "el modelo no encontró evidencia suficiente")

        # [7] Verificación de groundedness -----------------------------------
        g = self._verificar(texto, fragmentos, datos_vivos, ctx)
        self._paso(7, "verificación de groundedness", **g)
        if g["veredicto"] == "rechazado" or g["score"] < UMBRAL_GROUNDEDNESS:
            log.warning("groundedness insuficiente", extra={
                "conv": ctx.conv_id, "score": g["score"],
                "sin_respaldo": g["afirmaciones_sin_respaldo"]})
            return self._derivar(mensaje, ctx, historial,
                                 f"respuesta sin respaldo suficiente ({g['score']:.2f})")

        # [8] Salida ----------------------------------------------------------
        salida_bloqueada = self.safety.analizar_salida(texto).bloqueado
        self._paso(8, "seguridad de salida y traza",
                   resultado="bloqueada" if salida_bloqueada else "limpia")
        if salida_bloqueada:
            return self._derivar(mensaje, ctx, historial, "salida bloqueada por política")

        # Se muestran solo las fuentes que la respuesta cita.
        citadas = set(re.findall(r"\[(F\d+)\]", texto))
        fuentes = [{"id": f"F{i+1}", "titulo": f["titulo"], "uri": f["fuente_uri"],
                    "vigente_hasta": f["vigente_hasta"]}
                   for i, f in enumerate(fragmentos) if f"F{i+1}" in citadas]

        if not ruta["requiere_dato_vivo"]:
            self.cache_sem.guardar(mensaje, ctx.audiencia,
                                   {"texto": texto, "fuentes": fuentes,
                                    "groundedness": g["score"]})

        return Resultado(texto=texto, fuentes=fuentes, groundedness=g["score"])

    # ------------------------------------------------------------------ pasos
    def _rutear(self, mensaje: str, ctx: Contexto, historial: list[dict]) -> dict:
        r = self.llm.completar(
            Tarea.CLASIFICACION,
            [{"role": "system", "content": prompts.ROUTER},
             *historial[-4:],
             {"role": "user", "content": mensaje}],
            conv_id=ctx.conv_id, forzar_json=True)
        return self._normalizar_ruta(_json_o_none(r.texto))

    @staticmethod
    def _normalizar_ruta(d: dict | None) -> dict:
        """Ante un router roto o incompleto, el comportamiento seguro es el humano.
        Solo se aceptan las claves y los valores esperados."""
        if not isinstance(d, dict):
            return dict(RUTA_SEGURA)
        try:
            ruta = {
                "intencion": str(d["intencion"])[:40],
                "audiencia": str(d.get("audiencia", "desconocido")).strip().lower(),
                "requiere_dato_vivo": _bool(d["requiere_dato_vivo"]),
                "complejidad": "compleja" if str(d.get("complejidad")).lower() == "compleja"
                               else "simple",
                "requiere_humano": _bool(d["requiere_humano"]),
                "en_dominio": _bool(d["en_dominio"]),
                "confianza": max(0.0, min(1.0, float(d["confianza"]))),
            }
        except (KeyError, TypeError, ValueError):
            return dict(RUTA_SEGURA)
        if ruta["audiencia"] not in AUDIENCIAS_VALIDAS:
            ruta["audiencia"] = "desconocido"
        return ruta

    def _recuperar(self, consulta: str, ctx: Contexto) -> list[dict]:
        """Búsqueda híbrida con filtro de seguridad aplicado ANTES del modelo.

        El filtro por audiencia y sensibilidad va en la consulta al índice, no
        en el prompt. Un usuario no puede recuperar contenido restringido ni
        con el prompt perfecto, porque el contenido nunca entra al contexto.
        """
        # Edm.DateTimeOffset exige fecha-hora completa en UTC.
        ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        niveles = ["publico"]
        if ctx.autenticado:
            niveles.append("interno")

        # La audiencia la propone el router (un LLM): se valida contra la lista
        # cerrada antes de interpolarla. Sin esto, un mensaje manipulado podría
        # inyectar OData y saltarse el filtro de sensibilidad.
        audiencia = ctx.audiencia if ctx.audiencia in AUDIENCIAS_VALIDAS else "desconocido"
        filtro = (f"(audiencia/any(a: a eq '{audiencia}') or "
                  f"audiencia/any(a: a eq 'todos')) and "
                  f"search.in(sensibilidad, '{','.join(niveles)}', ',') and "
                  f"vigente_desde le {ahora} and vigente_hasta ge {ahora}")

        vector = self.llm.embeber([consulta])[0]
        return self.buscador.hibrida(
            texto=consulta, vector=vector, filtro=filtro,
            top_k=TOP_K, top_n=TOP_N_RERANK, semantic_ranker=True)

    def _generar(self, mensaje, ctx, historial, fragmentos, tarea):
        """Devuelve (texto, datos_vivos, completo). completo=False si se agotaron
        las vueltas de herramientas sin una respuesta final."""
        bloque = "\n\n".join(
            f"[F{i+1}] (fuente: {f['fuente_uri']} · vigente hasta {f['vigente_hasta']})\n"
            f"{f['contenido']}"
            for i, f in enumerate(fragmentos)) or "(sin fragmentos)"

        mensajes = [
            {"role": "system", "content": prompts.RESPUESTA},
            *historial[-6:],
            {"role": "user",
             "content": (f"AUDIENCIA: {ctx.audiencia}\n"
                         f"SESIÓN AUTENTICADA: {'sí' if ctx.autenticado else 'no'}\n\n"
                         f"FRAGMENTOS:\n{bloque}\n\nPREGUNTA DEL USUARIO:\n{mensaje}")},
        ]

        datos_vivos: list[dict] = []

        # Bucle de herramientas, acotado para evitar bucles infinitos.
        for _ in range(MAX_VUELTAS_TOOLS):
            r = self.llm.completar(tarea, mensajes, ctx.conv_id, tools=TOOLS)
            if not r.tool_calls:
                return r.texto, datos_vivos, True

            mensajes.append({"role": "assistant", "content": r.texto or None,
                             "tool_calls": r.tool_calls})
            for tc in r.tool_calls:
                nombre = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = None

                if nombre not in NOMBRES_TOOLS or not isinstance(args, dict):
                    salida = {"error": "llamada_invalida"}
                elif nombre in TOOLS_QUE_EXIGEN_AUTH and not ctx.autenticado:
                    salida = {"error": "autenticacion_requerida",
                              "mensaje": ("Para consultar el estado de tu solicitud "
                                          "necesito que inicies sesión.")}
                else:
                    salida = self.herramientas.ejecutar(nombre, args, ctx)
                    datos_vivos.append({"herramienta": nombre, "args": args,
                                        "salida": salida})

                mensajes.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": json.dumps(salida, ensure_ascii=False)})

        return "", datos_vivos, False

    def _verificar(self, texto, fragmentos, datos_vivos, ctx) -> dict:
        evidencia = "\n\n".join(f"[F{i+1}] {f['contenido']}"
                                for i, f in enumerate(fragmentos))
        if datos_vivos:
            evidencia += "\n\nDATOS EN VIVO:\n" + json.dumps(
                datos_vivos, ensure_ascii=False)
        r = self.llm.completar(
            Tarea.CLASIFICACION,
            [{"role": "system", "content": prompts.GROUNDEDNESS},
             {"role": "user", "content": f"FRAGMENTOS:\n{evidencia}\n\nRESPUESTA:\n{texto}"}],
            conv_id=ctx.conv_id, forzar_json=True, usar_cache=False)
        d = _json_o_none(r.texto)
        try:
            return {"score": max(0.0, min(1.0, float(d["score"]))),
                    "afirmaciones_sin_respaldo": list(d.get("afirmaciones_sin_respaldo") or []),
                    "veredicto": str(d["veredicto"]).lower()}
        except (KeyError, TypeError, ValueError):
            # Verificador roto = no hay verificación = no se responde.
            return {"score": 0.0, "afirmaciones_sin_respaldo": [],
                    "veredicto": "rechazado"}

    def _derivar(self, mensaje, ctx, historial, motivo, resumir: bool = True,
                 humano_pedido: bool = False) -> Resultado:
        """Derivación con contexto. El asesor no empieza de cero: recibe el caso
        resumido, lo que el bot ya respondió y lo que queda pendiente."""
        paquete = None
        if resumir:
            try:
                r = self.llm.completar(
                    Tarea.CLASIFICACION,
                    [{"role": "system", "content": prompts.HANDOFF},
                     {"role": "user", "content": json.dumps(
                         [*historial, {"role": "user", "content": mensaje}],
                         ensure_ascii=False)}],
                    conv_id=ctx.conv_id, forzar_json=True, usar_cache=False)
                paquete = _json_o_none(r.texto)
            except Exception:  # noqa: BLE001 - el resumen es opcional
                log.warning("no se pudo resumir el handoff conv=%s", ctx.conv_id)
        if not isinstance(paquete, dict):
            paquete = {"resumen": mensaje[:200], "pendiente": motivo,
                       "urgencia": "media"}

        paquete |= {"motivo_derivacion": motivo, "canal": ctx.canal,
                    "conv_id": ctx.conv_id}
        try:
            self.herramientas.crear_caso_crm(paquete, ctx)   # cola en Teams
        except Exception:  # noqa: BLE001
            # El caso no se pierde: queda en el log para reproceso.
            log.exception("no se pudo crear el caso en CRM conv=%s", ctx.conv_id)
        self._paso(9, "derivación a humano", motivo=motivo, paquete=paquete)

        if humano_pedido:
            texto = ("Claro. Le paso tu conversación a un asesor de ESIC con todo "
                     "el contexto, para que no tengas que repetir nada. Te responde "
                     "hoy mismo en horario hábil. ¿Me confirmas tu correo?")
        elif motivo == "error técnico":
            texto = ("Tuve un problema para procesar tu consulta. Le paso tu caso "
                     "a un asesor de admisiones con el contexto. ¿Me confirmas tu correo?")
        else:
            texto = ("Prefiero no darte un dato que no tengo confirmado. "
                     "Le paso tu consulta a un asesor de admisiones con todo el "
                     "contexto; te responde hoy mismo en horario hábil. "
                     "¿Me confirmas tu correo?")
        return Resultado(texto=texto, fuentes=[], derivar_a_humano=True,
                         motivo_derivacion=motivo, paquete_handoff=paquete)

    def _registrar_vacio(self, mensaje: str, ctx: Contexto) -> None:
        """Toda pregunta sin evidencia es un vacío de contenido con dueño.
        Esto convierte cada falla en una tarea concreta para Knowledge Ops."""
        self.herramientas.registrar_vacio_conocimiento({
            "pregunta": mensaje, "audiencia": ctx.audiencia,
            "canal": ctx.canal, "conv_id": ctx.conv_id})
