# -*- coding: utf-8 -*-
"""
simulados.py — Servicios de ESIC simulados en memoria para el demo.

Sustituyen a Azure AI Search, las APIs del ERP / SIA / CRM, Content Safety,
Redis y Document Intelligence. El orquestador y el validador son EXACTAMENTE
los mismos que irían a producción: solo cambia lo que se les inyecta.

Incluye un LLM simulado y determinista (`ClienteLLMSimulado`) con el mismo
contrato que el SDK de OpenAI, para que el demo corra sin clave ni red.
Con --proveedor gemini se usa un modelo real en su lugar.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

from demo import base_conocimiento as bc
from escenario1_chatbot import prompts

# ----------------------------------------------------------------- texto
STOP = set("""a al algo como con cual cuales cuando de del desde donde el ella en
entre era es esa ese eso esta este esto estoy fue ha hay la las le les lo los
mas me mi mis muy ni no nos o os para pero por que quien se si sin sobre su sus
te tengo tiene tienen tu tus un una uno unos y ya yo hola quiero saber puedo
gracias favor bien estan esta hace hacer ser""".split())


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def tokens(t: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", normalizar(t))
            if w not in STOP and len(w) > 2]


def _raiz(w: str) -> str:
    # Stemming mínimo para español: suficiente para el demo.
    for suf in ("aciones", "acion", "mente", "idad", "ados", "idas", "ando",
                "iendo", "es", "os", "as", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def raices(t: str) -> list[str]:
    return [_raiz(w) for w in tokens(t)]


def embedding_hash(texto: str, dim: int = 256) -> list[float]:
    """Embedding determinista (hashing trick). Sustituye a text-embedding-3-large."""
    v = [0.0] * dim
    rs = raices(texto)
    for g in rs + [a + "_" + b for a, b in zip(rs, rs[1:])]:
        h = int(hashlib.md5(g.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 8) % 2 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def coseno(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ------------------------------------------------------- Azure AI Search
class BuscadorMemoria:
    """Búsqueda híbrida en memoria: BM25 + vector, fusionados con RRF.
    Interpreta el filtro OData que construye el orquestador, así el demo
    comprueba de verdad que el filtro de seguridad funciona."""

    PATRON = re.compile(
        r"audiencia/any\(a: a eq '(?P<aud>[a-z]+)'\).*"
        r"search\.in\(sensibilidad, '(?P<niv>[a-z,]+)', ','\).*"
        r"vigente_desde le (?P<d>\S+) and vigente_hasta ge (?P<h>\S+)$")

    def __init__(self, fragmentos: list[dict], min_coincidencias: int = 2):
        self.docs = fragmentos
        self.min = min_coincidencias
        self._tok = [raices(f["titulo"] + " " + f["ruta"] + " " + f["contenido"])
                     for f in fragmentos]
        self._vec = [embedding_hash(f["ruta"] + " " + f["contenido"]) for f in fragmentos]
        n = len(fragmentos)
        self._avg = sum(len(t) for t in self._tok) / n
        self._df: dict[str, int] = {}
        for t in self._tok:
            for w in set(t):
                self._df[w] = self._df.get(w, 0) + 1
        self.ultimo_excluidos: list[dict] = []

    def _permitido(self, f: dict, filtro: str) -> str | None:
        m = self.PATRON.search(filtro)
        if not m:
            raise ValueError(f"filtro OData con formato inesperado: {filtro}")
        ahora = m["d"][:10]
        if not (set(f["audiencia"]) & {m["aud"], "todos"}):
            return "audiencia"
        if f["sensibilidad"] not in m["niv"].split(","):
            return "sensibilidad"
        if not (f["vigente_desde"] <= ahora <= f["vigente_hasta"]):
            return "vencido"
        return None

    def _bm25(self, q: list[str], i: int, k1=1.4, b=0.75) -> tuple[float, int]:
        doc, n, s, hits = self._tok[i], len(self.docs), 0.0, 0
        for w in set(q):
            tf = doc.count(w)
            if not tf:
                continue
            hits += 1
            idf = math.log(1 + (n - self._df[w] + 0.5) / (self._df[w] + 0.5))
            s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(doc) / self._avg))
        return s, hits

    def hibrida(self, texto, vector, filtro, top_k, top_n, semantic_ranker=True):
        q = raices(texto)
        qv = embedding_hash(texto)
        cand, self.ultimo_excluidos = [], []
        for i, f in enumerate(self.docs):
            s, hits = self._bm25(q, i)
            if hits < self.min:
                continue
            motivo = self._permitido(f, filtro)
            if motivo:
                self.ultimo_excluidos.append({"titulo": f["titulo"], "motivo": motivo})
                continue
            cand.append((i, s, coseno(qv, self._vec[i])))
        por_lex = sorted(cand, key=lambda c: -c[1])[:top_k]
        por_vec = sorted(cand, key=lambda c: -c[2])[:top_k]
        rrf: dict[int, float] = {}
        for lista in (por_lex, por_vec):
            for pos, c in enumerate(lista):
                rrf[c[0]] = rrf.get(c[0], 0) + 1 / (60 + pos)
        orden = sorted(rrf, key=lambda i: -rrf[i])[:top_n]
        mejor = max(rrf.values()) if rrf else 1
        return [{**self.docs[i], "score": round(0.6 + 0.35 * rrf[i] / mejor
                                                 - 0.03 * pos, 2)}
                for pos, i in enumerate(orden)]


# ------------------------------------------------ APIs en vivo y CRM
class HerramientasSimuladas:
    def __init__(self):
        self.casos_crm: list[dict] = []
        self.vacios: list[dict] = []

    def ejecutar(self, nombre: str, args: dict, ctx) -> dict:
        cod = str(args.get("codigo_programa", "")).upper().strip()
        if nombre == "consultar_precio_vigente":
            return bc.DATOS_VIVOS["precios"].get(cod, {"error": "programa_no_encontrado"})
        if nombre == "consultar_fechas_admision":
            return bc.DATOS_VIVOS["fechas"].get(cod, {"error": "programa_no_encontrado"})
        if nombre == "consultar_estado_solicitud":
            return {"estado": "en revisión documental", "actualizado": bc.HOY.isoformat()}
        if nombre == "buscar_vacantes_egresados":
            return {"vacantes": [{"cargo": "Analista de CX", "empresa": "Empresa demo S.A.S.",
                                  "ciudad": args.get("ciudad", "Medellín")}]}
        return {"error": "herramienta_desconocida"}

    def crear_caso_crm(self, paquete: dict, ctx) -> None:
        self.casos_crm.append({"id": f"CASO-{len(self.casos_crm) + 1:04d}", **paquete})

    def registrar_vacio_conocimiento(self, d: dict) -> None:
        self.vacios.append({"id": f"VACIO-{len(self.vacios) + 1:03d}",
                            "dueno": "Knowledge Ops", **d})


@dataclass
class Veredicto:
    bloqueado: bool
    categoria: str = ""


class SafetySimulado:
    """Sustituto de Content Safety + Prompt Shields (detección por patrones)."""
    INYECCION = re.compile(
        r"ignora (tus|todas|las) (instrucciones|reglas)|olvida (tus|las) instrucciones|"
        r"prompt de sistema|system prompt|act[uú]a como|modo desarrollador|jailbreak",
        re.I)

    def analizar_entrada(self, texto: str) -> Veredicto:
        if self.INYECCION.search(texto):
            return Veredicto(True, "prompt_injection")
        return Veredicto(False)

    def analizar_salida(self, texto: str) -> Veredicto:
        return Veredicto(False)


class CacheSemantica:
    """Caché semántica por audiencia (Redis + vector en producción)."""
    UMBRAL = 0.94

    def __init__(self, llm):
        self.llm = llm
        self._items: list[tuple[str, list[float], dict]] = []

    def buscar(self, mensaje: str, audiencia: str):
        v = self.llm.embeber([mensaje])[0]
        mejor, sim = None, 0.0
        for aud, vec, val in self._items:
            if aud != audiencia:
                continue
            s = coseno(v, vec)
            if s > sim:
                mejor, sim = val, s
        if mejor and sim >= self.UMBRAL:
            return {**mejor, "similitud": round(sim, 3)}
        return None

    def guardar(self, mensaje: str, audiencia: str, valor: dict) -> None:
        self._items.append((audiencia, self.llm.embeber([mensaje])[0], valor))


# ------------------------------------------------------ LLM simulado
def _usage(mensajes, salida: str) -> dict:
    tin = sum(len(str(m.get("content") or "")) for m in mensajes) // 4
    return {"prompt_tokens": tin, "completion_tokens": max(1, len(salida) // 4)}


def _resp(mensajes, contenido: str | None = None, tool_calls=None):
    from comun.cliente_http import _a_obj
    msg = {"role": "assistant", "content": contenido, "tool_calls": tool_calls}
    return _a_obj({"choices": [{"message": msg, "finish_reason": "stop"}],
                   "usage": _usage(mensajes, contenido or json.dumps(tool_calls))})


TEMAS = {
    "precio": ("precio", "cuesta", "costo", "valor", "cuota", "pago", "pagar", "financ"),
    "descuento": ("descuento", "beneficio", "beca"),
    "fechas": ("cierre", "cierran", "inscrip", "cupo", "fecha", "cuando", "inicio", "empiez"),
    "empleo": ("coloc", "emple", "trabaj", "salida"),
    "requisitos": ("requisit", "necesito", "exige", "ingresar", "admision", "piden"),
    "plan": ("plan", "modulo", "materia", "dura", "horario", "modalidad"),
    "certificado": ("certificado", "constancia"),
}


def temas_de(texto: str) -> list[str]:
    t = normalizar(texto)
    return [k for k, claves in TEMAS.items() if any(c in t for c in claves)]


class ClienteLLMSimulado:
    """Motor determinista con el contrato del SDK de OpenAI.

    No 'entiende' lenguaje: aplica reglas explícitas. Existe para que el demo
    muestre el flujo completo sin red. `alucinar=True` fuerza una afirmación
    inventada en la siguiente respuesta, para demostrar el verificador."""

    def __init__(self):
        self.alucinar = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))
        self.embeddings = SimpleNamespace(create=self._embeber)

    # -------------------------------------------------------------- API
    def _embeber(self, model, input, **_):
        from comun.cliente_http import _a_obj
        return _a_obj({"data": [{"embedding": embedding_hash(t)} for t in input]})

    def _crear(self, model, messages, **kw):
        sistema = messages[0]["content"] if messages else ""
        if sistema == prompts.ROUTER:
            return _resp(messages, json.dumps(self._rutear(messages[-1]["content"]),
                                              ensure_ascii=False))
        if sistema == prompts.RESPUESTA:
            return self._generar(messages, kw.get("tools") or [])
        if sistema == prompts.GROUNDEDNESS:
            return _resp(messages, json.dumps(self._verificar(messages[-1]["content"]),
                                              ensure_ascii=False))
        if sistema == prompts.HANDOFF:
            return _resp(messages, json.dumps(self._handoff(messages[-1]["content"]),
                                              ensure_ascii=False))
        if sistema.startswith("Redacta un correo"):
            return _resp(messages, self._correo(messages[-1]["content"]))
        return _resp(messages, "")

    # ------------------------------------------------------------ router
    def _rutear(self, mensaje: str) -> dict:
        t = normalizar(mensaje)
        fuera = any(w in t for w in ("partido", "futbol", "receta", "clima", "bitcoin",
                                      "horoscopo", "pelicula"))
        humano = any(w in t for w in ("hablar con una persona", "hablar con alguien",
                                      "asesor humano", "queja", "reclamo"))
        ts = temas_de(mensaje)
        if "precio" in ts or "descuento" in ts:
            intencion = "financiacion"
        elif "requisitos" in ts or "fechas" in ts:
            intencion = "admisiones"
        elif "empleo" in ts:
            intencion = "empleabilidad"
        elif "certificado" in ts:
            intencion = "servicios_estudiante"
        elif humano:
            intencion = "queja_reclamo" if "queja" in t or "reclamo" in t else "admisiones"
        elif fuera:
            intencion = "fuera_de_dominio"
        else:
            intencion = "info_programa"
        if any(w in t for w in ("me gradue", "soy egresad", "como egresad", "exalumn")):
            audiencia = "egresado"
        elif any(w in t for w in ("soy estudiante", "estoy cursando", "mi semestre")):
            audiencia = "estudiante"
        elif any(w in t for w in ("mi empresa", "mis empleados", "corporativ")):
            audiencia = "empresa"
        elif any(w in t for w in ("quiero estudiar", "me interesa", "aspir", "inscribirme")):
            audiencia = "aspirante"
        else:
            audiencia = "desconocido"
        return {
            "intencion": intencion,
            "audiencia": audiencia,
            "requiere_dato_vivo": bool({"precio", "descuento", "fechas"} & set(ts)),
            "complejidad": "compleja" if len(ts) >= 3 else "simple",
            "requiere_humano": humano,
            "en_dominio": not fuera,
            "confianza": 0.94 if ts or fuera or humano else 0.72,
        }

    # -------------------------------------------------------- generación
    @staticmethod
    def _fragmentos(user: str) -> list[tuple[str, str]]:
        return re.findall(r"\[(F\d+)\] \(fuente:[^\n]*\)\n([^\n]+)", user)

    def _generar(self, messages, tools):
        user = next(m["content"] for m in messages if m["role"] == "user"
                    and "PREGUNTA DEL USUARIO" in str(m["content"]))
        pregunta = user.split("PREGUNTA DEL USUARIO:\n", 1)[1]
        fr = self._fragmentos(user)
        ts = temas_de(pregunta)
        vivos = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        ya_llamo = any(m["role"] == "tool" for m in messages)
        # El programa se toma de la PREGUNTA; solo si no se nombra, del primer fragmento.
        pn = normalizar(pregunta)
        cod = next((k for k, v in bc.PROGRAMAS.items()
                    if normalizar(v).replace("master en ", "") in pn), "")
        if not cod:
            cods = [c for _, txt in fr for c in re.findall(r"código ([A-Z]{3})", txt)]
            cod = cods[0] if cods else ""
        # Solo se usan fragmentos del mismo programa (o generales).
        fr = [(fid, txt) for fid, txt in fr
              if not re.search(r"código [A-Z]{3}", txt) or f"código {cod}" in txt]

        # 1ª vuelta: pedir datos en vivo si la pregunta los necesita.
        if tools and not ya_llamo and cod and ({"precio", "descuento", "fechas"} & set(ts)):
            llamadas = []
            if {"precio", "descuento"} & set(ts):
                llamadas.append(("consultar_precio_vigente",
                                 {"codigo_programa": cod, "cohorte": bc.COHORTE_ABIERTA}))
            if "fechas" in ts:
                llamadas.append(("consultar_fechas_admision", {"codigo_programa": cod}))
            tcs = [{"id": f"call_{i+1}", "type": "function",
                    "function": {"name": n, "arguments": json.dumps(a)}}
                   for i, (n, a) in enumerate(llamadas)]
            return _resp(messages, None, tcs)

        frases = []
        precio = next((v for v in vivos if "valor_matricula_cop" in v), None)
        fechas = next((v for v in vivos if "cierre_inscripciones" in v), None)
        nombre = bc.PROGRAMAS.get(cod, "programa")
        egresado = "AUDIENCIA: egresado" in user

        if "descuento" in ts and precio:
            quien = "Como egresado de ESIC tienes" if egresado else "Hay"
            frases.append(f"{quien} un descuento del {precio['descuento_egresado_pct']}% "
                          f"sobre la matrícula del {nombre} [DV].")
        if "precio" in ts and precio:
            frases.append(f"Para la cohorte {precio['cohorte']}, la matrícula es de "
                          f"${precio['valor_matricula_cop']:,}".replace(",", ".") +
                          f" y se puede pagar en {precio['cuotas_sin_interes']} cuotas [DV].")
        for tema, clave in (("requisitos", "requiere"), ("plan", "dura"),
                            ("empleo", "trabajando"), ("certificado", "certificados")):
            if tema not in ts:
                continue
            hecho = False
            for fid, txt in fr:
                for oracion in re.split(r"(?<=\.)\s+", txt):
                    if clave in oracion:
                        frases.append(f"{oracion.rstrip('.')} [{fid}].")
                        hecho = True
                        break
                if hecho:
                    break
            if not hecho and tema == "empleo":
                if self.alucinar:
                    frases.append(f"Además, el 100% de los egresados del {nombre} "
                                  f"consigue empleo antes de graduarse.")
                    self.alucinar = False
                else:
                    frases.append("No tengo cifras de empleabilidad confirmadas para "
                                  "ese programa.")
        if "fechas" in ts and fechas:
            frases.append(f"Las inscripciones cierran el {fechas['cierre_inscripciones']} "
                          f"y quedan {fechas['cupos_disponibles']} cupos [DV].")
        if not frases:
            if fr:
                fid, txt = fr[0]
                primera = re.split(r"(?<=\.)\s+", txt)[0].rstrip(".")
                frases.append(f"{primera} [{fid}].")
            else:
                frases.append("No tengo esa información confirmada. Te conecto con un "
                              "asesor de admisiones que puede darte el dato exacto.")
        frases.append("¿Quieres que te agende una sesión con un asesor de másteres "
                      "esta semana?")
        return _resp(messages, " ".join(frases))

    # -------------------------------------------------------- verificador
    @staticmethod
    def _verificar(contenido: str) -> dict:
        evidencia, respuesta = contenido.split("\n\nRESPUESTA:\n", 1)
        ev_norm = normalizar(evidencia)
        ev_nums = set(re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*", evidencia))
        ev_raices = set(raices(evidencia))
        sin_respaldo, total, ok = [], 0, 0
        for oracion in re.split(r"(?<=[.?])\s+", respuesta.strip()):
            if oracion.endswith("?") or not oracion:
                continue                         # cierre: se ignora
            limpia = re.sub(r"\[(F\d+|DV)\]", "", oracion)
            total += 1
            nums = [re.sub(r"[.,]", "", n).rstrip("0") or "0"
                    for n in re.findall(r"\d[\d.,]*\d|\d", limpia)]
            nums_ok = all(any(e.startswith(n) or n == e.rstrip("0") for e in ev_nums)
                          for n in nums)
            rs = [r for r in raices(limpia) if len(r) > 3]
            cobertura = (sum(r in ev_raices for r in rs) / len(rs)) if rs else 1.0
            niega = "no tengo" in normalizar(limpia)
            if niega or (nums_ok and cobertura >= 0.6):
                ok += 1
            else:
                sin_respaldo.append(oracion.strip())
        score = round(ok / total, 2) if total else 1.0
        critico = any(re.search(r"\d", s) for s in sin_respaldo)
        veredicto = ("rechazado" if critico else
                     "aprobado" if score >= 0.7 else "revisar")
        return {"score": 0.0 if critico and score > 0.3 else score,
                "afirmaciones_sin_respaldo": sin_respaldo, "veredicto": veredicto}

    # ------------------------------------------------------------ handoff
    @staticmethod
    def _handoff(contenido: str) -> dict:
        turnos = json.loads(contenido)
        ultimo = turnos[-1]["content"]
        ts = temas_de(ultimo)
        molesto = any(w in normalizar(ultimo) for w in ("queja", "reclamo", "molest"))
        return {
            "resumen": ultimo[:160],
            "datos_recogidos": {},
            "ya_respondido": [],
            "pendiente": ("resolver: " + ", ".join(ts)) if ts else "atender la solicitud",
            "urgencia": "alta" if molesto else "media",
            "estado_animo": "molesto" if molesto else "neutral",
        }

    # ------------------------------------------------------------- correo
    @staticmethod
    def _correo(contenido: str) -> str:
        d = json.loads(contenido)
        lista = "\n".join(f"- {p}" for p in d["problemas"])
        return ("Hola. Gracias por avanzar en tu proceso de admisión a ESIC Medellín. "
                "Para continuar necesitamos que revises lo siguiente:\n"
                f"{lista}\n"
                "Puedes volver a cargar los documentos, en PDF o JPG legibles, aquí: "
                f"{d['enlace_de_carga']}\n"
                "Si tienes dudas, responde este correo y te ayudamos.")


# ----------------------------------------------- Escenario 2 (servicios)
DOCUMENTOS_DEMO: dict[str, dict] = {}


def archivo(nombre: str, tipo: str, campos: dict, confianza: float = 0.95,
            paginas: int = 1, meta: dict | None = None, contenido: bytes | None = None):
    b = contenido or f"{nombre}|{json.dumps(campos, sort_keys=True)}".encode()
    DOCUMENTOS_DEMO[hashlib.sha256(b).hexdigest()] = {
        "tipo": tipo, "campos": campos, "confianza": confianza,
        "paginas": paginas, "meta": meta or {}}
    return {"nombre": nombre, "bytes": b, "paginas": paginas}


class DocIntelSimulado:
    def _d(self, b: bytes) -> dict:
        return DOCUMENTOS_DEMO[hashlib.sha256(b).hexdigest()]

    def clasificar(self, b: bytes, pista: str = "") -> str:
        return self._d(b)["tipo"]

    def analizar(self, b: bytes, modelo: str) -> dict:
        d = self._d(b)
        return {"campos": d["campos"], "confianza_promedio": d["confianza"],
                "paginas": d["paginas"], "modelo": modelo}

    def metadatos(self, b: bytes) -> dict:
        return self._d(b)["meta"]


class CRMSimulado:
    def obtener_solicitud(self, sid: str) -> dict:
        return bc.SOLICITUDES_CRM.get(sid, {})


class SIASimulado:
    SNIES_VALIDOS = {"104312", "91245", "3456"}

    def verificar_programa_snies(self, snies: str, institucion: str | None) -> bool:
        return str(snies) in self.SNIES_VALIDOS


class StorageSimulado:
    def __init__(self):
        self._hashes: dict[str, dict] = {}

    def registrar(self, b: bytes, solicitud_id: str) -> None:
        self._hashes[hashlib.sha256(b).hexdigest()] = {
            "solicitud_id": solicitud_id,
            "cargado_en": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    def buscar_por_hash(self, h: str):
        return self._hashes.get(h)
