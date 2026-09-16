# -*- coding: utf-8 -*-
"""
validador.py — Escenario 2: validación automática de documentos de admisión

Línea base: ~2 h por 20 solicitudes de revisión manual, más los ciclos de correo
por documentos incompletos (que es donde realmente se va el tiempo).

Postura de diseño, explícita porque es la pregunta trampa del caso:
ESTE SISTEMA NO DETECTA FALSIFICACIONES. Ningún sistema comercial lo hace de
forma confiable sobre un PDF escaneado. Lo que sí hace es calcular un SCORE DE
RIESGO a partir de cinco capas de evidencia independientes, y enrutar: aprobar
lo que es claramente correcto, devolver lo que es claramente incompleto, y poner
frente a un humano —con los hallazgos ya señalados— solo lo dudoso.

El valor no está en reemplazar el criterio humano: está en que el humano deje de
revisar las 17 solicitudes correctas para concentrarse en las 3 que importan.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

from comun.llm_gateway import Tarea

VERSION_VALIDADOR = "3.2.0"
UMBRAL_AUTO_APROBACION = 85
UMBRAL_REVISION        = 50
UMBRAL_SIMILITUD_NOMBRE = 0.85

log = logging.getLogger("fabrica.e2")


class TipoDoc(str, Enum):
    CEDULA        = "cedula"
    ACTA_GRADO    = "acta_grado"
    DIPLOMA       = "diploma"
    TRANSCRIPT    = "transcript_notas"
    CERT_LABORAL  = "certificado_laboral"
    FOTO          = "fotografia"
    DESCONOCIDO   = "desconocido"


class Decision(str, Enum):
    AUTO_APROBADO   = "auto_aprobado"      # score >= 85 y sin hallazgos críticos
    REVISION_HUMANA = "revision_humana"    # 50 <= score < 85, o cualquier señal de riesgo
    DEVOLVER        = "devolver"           # score < 50 por causas que el aspirante puede corregir


# Modelo de Document Intelligence por tipo. Elegir el correcto es la diferencia
# entre USD 1,50 y USD 30 por 1.000 páginas (ver Documento 4).
MODELO_DI = {
    TipoDoc.CEDULA:       "prebuilt-idDocument",
    TipoDoc.TRANSCRIPT:   "prebuilt-layout",
    TipoDoc.CERT_LABORAL: "prebuilt-layout",
    TipoDoc.ACTA_GRADO:   "esic-acta-grado-co-v3",   # modelo custom entrenado
    TipoDoc.DIPLOMA:      "esic-diploma-co-v2",      # modelo custom entrenado
    TipoDoc.FOTO:         None,                      # solo validación de imagen
    TipoDoc.DESCONOCIDO:  None,                      # no se extrae: se señala
}

# USD por página, pay-as-you-go (ver Documento 4). Clasificación incluida.
PRECIO_PAGINA_USD = {"prebuilt-idDocument": 0.010, "prebuilt-layout": 0.010,
                     "custom": 0.030, "clasificacion": 0.003}

NOMBRE_DOC = {
    "cedula": "cédula de ciudadanía", "acta_grado": "acta de grado",
    "diploma": "diploma", "transcript_notas": "certificado de notas",
    "certificado_laboral": "certificado laboral", "fotografia": "fotografía",
}

# Hallazgos que el aspirante puede corregir por sí mismo. Solo estos se le
# comunican. Las señales de riesgo (editor de imágenes, capas superpuestas,
# duplicados, documento que no coincide) van EXCLUSIVAMENTE al revisor humano:
# describirlas al aspirante sería insinuar fraude.
CORREGIBLES_POR_ASPIRANTE = {
    "DOC_FALTANTE", "OCR_BAJA_CONFIANZA", "DOC_NO_RECONOCIDO", "SIN_PROMEDIO",
    "CEDULA_FORMATO", "FECHA_ILEGIBLE", "SIN_INSTITUCION",
}


@dataclass
class Hallazgo:
    codigo: str
    severidad: str            # info | advertencia | critico
    mensaje: str              # descripción para el revisor
    peso: int = 0             # puntos que resta del score (negativo = suma)
    evidencia: dict = field(default_factory=dict)
    documento: str = ""       # archivo donde se detectó, si aplica

    @property
    def corregible(self) -> bool:
        return self.codigo in CORREGIBLES_POR_ASPIRANTE


@dataclass
class ResultadoDoc:
    tipo: TipoDoc
    campos: dict[str, Any]
    confianza_ocr: float
    hallazgos: list[Hallazgo] = field(default_factory=list)
    hash_archivo: str = ""
    nombre_archivo: str = ""
    paginas: int = 0
    costo_usd: float = 0.0


@dataclass
class ResultadoSolicitud:
    solicitud_id: str
    score: int
    decision: Decision
    documentos: list[ResultadoDoc]
    hallazgos: list[Hallazgo]       # TODOS: por documento + cruzados + faltantes
    faltantes: list[str]
    mensaje_aspirante: str = ""
    trazabilidad: dict = field(default_factory=dict)


DOCS_REQUERIDOS = {
    "maestria": [TipoDoc.CEDULA, TipoDoc.ACTA_GRADO, TipoDoc.TRANSCRIPT, TipoDoc.FOTO],
    "pregrado": [TipoDoc.CEDULA, TipoDoc.ACTA_GRADO, TipoDoc.FOTO],
    "ejecutivo": [TipoDoc.CEDULA, TipoDoc.CERT_LABORAL],
}


class ValidadorDocumental:
    def __init__(self, doc_intel, llm, crm, sia, storage):
        self.di, self.llm = doc_intel, llm
        self.crm, self.sia, self.storage = crm, sia, storage

    # =======================================================================
    def validar(self, solicitud_id: str, archivos: list[dict],
                programa_tipo: str, url_carga: str = "") -> ResultadoSolicitud:
        if programa_tipo not in DOCS_REQUERIDOS:
            raise ValueError(f"tipo de programa desconocido: {programa_tipo}")
        t0 = time.perf_counter()
        docs = [self._procesar(a) for a in archivos]

        cruzados = list(self._cruzar(docs, solicitud_id))
        faltantes = self._faltantes(docs, programa_tipo)
        for f in faltantes:
            cruzados.append(Hallazgo(
                "DOC_FALTANTE", "critico",
                f"Falta el documento: {NOMBRE_DOC.get(f, f)}.", peso=100,
                evidencia={"tipo": f}))

        todos = [h for d in docs for h in d.hallazgos] + cruzados
        score = self._score(docs, cruzados)
        decision = self._decidir(score, todos)

        huella = hashlib.sha256(
            "|".join(sorted(d.hash_archivo for d in docs)).encode()).hexdigest()
        res = ResultadoSolicitud(
            solicitud_id=solicitud_id, score=score, decision=decision,
            documentos=docs, hallazgos=todos, faltantes=faltantes,
            trazabilidad={
                "evaluado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "version_validador": VERSION_VALIDADOR,
                "huella_documentos": huella,     # base de la llave de idempotencia
                "documentos": [{"archivo": d.nombre_archivo, "tipo": d.tipo.value,
                                "modelo": MODELO_DI.get(d.tipo), "sha256": d.hash_archivo}
                               for d in docs],
                "paginas_procesadas": sum(d.paginas for d in docs),
                "costo_di_usd": round(sum(d.costo_usd for d in docs), 4),
                "duracion_ms": int((time.perf_counter() - t0) * 1000),
            })

        # Se redacta el correo cuando hay algo que el aspirante puede corregir y la
        # solicitud no quedó aprobada: lo usa el flujo tanto al devolver como cuando
        # el revisor humano decide devolver.
        if decision != Decision.AUTO_APROBADO and any(
                h.corregible and h.severidad != "info" for h in todos):
            res.mensaje_aspirante = self._redactar(res, url_carga)

        log.info("solicitud evaluada", extra={
            "solicitud": solicitud_id, "score": score, "decision": decision.value,
            "criticos": sum(1 for h in todos if h.severidad == "critico")})
        return res

    @staticmethod
    def _decidir(score: int, hallazgos: list[Hallazgo]) -> Decision:
        """El score ordena; dos reglas duras lo acotan.
        1. Con un hallazgo crítico nunca se auto-aprueba (una firma digital no
           compensa un nombre que no coincide).
        2. Solo se devuelve automáticamente lo que el aspirante puede corregir.
           Cualquier señal de riesgo va a un humano: el sistema no rechaza."""
        criticos = [h for h in hallazgos if h.severidad == "critico"]
        riesgo = [h for h in hallazgos
                  if h.severidad != "info" and not h.corregible and h.peso > 0]
        if score >= UMBRAL_AUTO_APROBACION and not criticos:
            return Decision.AUTO_APROBADO
        if score < UMBRAL_REVISION and not riesgo:
            return Decision.DEVOLVER
        return Decision.REVISION_HUMANA

    # ============================================== CAPA 1: extracción (OCR)
    def _procesar(self, archivo: dict) -> ResultadoDoc:
        contenido: bytes = archivo["bytes"]
        nombre = archivo.get("nombre", "")
        h = hashlib.sha256(contenido).hexdigest()

        tipo = self._clasificar(archivo)
        modelo = MODELO_DI.get(tipo)
        paginas = int(archivo.get("paginas", 1))
        costo = paginas * PRECIO_PAGINA_USD["clasificacion"]

        if tipo is TipoDoc.DESCONOCIDO:
            doc = ResultadoDoc(tipo, {}, 0.0, hash_archivo=h, nombre_archivo=nombre,
                               paginas=paginas, costo_usd=costo)
            doc.hallazgos.append(Hallazgo(
                "DOC_NO_RECONOCIDO", "advertencia",
                "No se reconoce qué documento es este archivo.", peso=30,
                documento=nombre))
            return doc
        if modelo is None:
            return ResultadoDoc(tipo, {}, 1.0, hash_archivo=h, nombre_archivo=nombre,
                                paginas=paginas, costo_usd=costo)

        salida = self.di.analizar(contenido, modelo=modelo)
        campos = salida["campos"]
        conf = float(salida["confianza_promedio"])
        paginas = int(salida.get("paginas", paginas))
        precio = PRECIO_PAGINA_USD.get(modelo, PRECIO_PAGINA_USD["custom"])
        costo = paginas * (precio + PRECIO_PAGINA_USD["clasificacion"])

        doc = ResultadoDoc(tipo, campos, conf, hash_archivo=h, nombre_archivo=nombre,
                           paginas=paginas, costo_usd=costo)

        # Confianza baja de OCR: no es fraude, es un escaneo malo. Se distingue
        # porque el mensaje al aspirante es completamente distinto.
        if conf < 0.75:
            doc.hallazgos.append(Hallazgo(
                "OCR_BAJA_CONFIANZA", "advertencia",
                "El documento se ve borroso o mal escaneado.",
                peso=25, evidencia={"confianza": round(conf, 3)}))

        doc.hallazgos.extend(self._integridad(archivo, tipo))
        doc.hallazgos.extend(self._reglas_del_tipo(tipo, campos))
        for hz in doc.hallazgos:
            hz.documento = nombre
        return doc

    def _clasificar(self, archivo: dict) -> TipoDoc:
        """Clasificación por visión. El nombre del archivo es una pista, no una
        fuente de verdad: los aspirantes suben 'documento1.pdf' todo el tiempo."""
        pista = archivo.get("nombre", "").lower()
        etiqueta = self.di.clasificar(archivo["bytes"], pista=pista)
        try:
            return TipoDoc(etiqueta)
        except ValueError:
            return TipoDoc.DESCONOCIDO

    # ================================ CAPA 2: integridad técnica del archivo
    def _integridad(self, archivo: dict, tipo: TipoDoc) -> list[Hallazgo]:
        """Señales objetivas del contenedor, no juicios sobre el contenido.
        Ninguna prueba nada por sí sola; suman evidencia."""
        out: list[Hallazgo] = []
        meta = self.di.metadatos(archivo["bytes"])

        editores = {"photoshop", "gimp", "canva", "illustrator", "paint.net"}
        productor = (meta.get("producer", "") + meta.get("creator", "")).lower()
        if any(e in productor for e in editores):
            out.append(Hallazgo(
                "META_EDITOR_IMAGEN", "advertencia",
                "El archivo fue generado con un editor de imágenes.", peso=20,
                evidencia={"producer": meta.get("producer")}))

        if meta.get("paginas_con_capas_superpuestas"):
            out.append(Hallazgo(
                "PDF_CAPAS_SUPERPUESTAS", "advertencia",
                "El PDF tiene texto superpuesto sobre la imagen original.", peso=30,
                evidencia={"paginas": meta["paginas_con_capas_superpuestas"]}))

        if meta.get("fecha_modificacion") and meta.get("fecha_creacion"):
            if meta["fecha_modificacion"] < meta["fecha_creacion"]:
                out.append(Hallazgo(
                    "META_FECHAS_INCOHERENTES", "advertencia",
                    "Las fechas internas del archivo son incoherentes.", peso=15))

        # Firma digital válida: evidencia FUERTE a favor. Resta riesgo.
        if meta.get("firma_digital_valida"):
            out.append(Hallazgo(
                "FIRMA_DIGITAL_VALIDA", "info",
                "El documento tiene firma digital válida.", peso=-25,
                evidencia={"emisor": meta.get("firmante")}))
        return out

    # ==================================== CAPA 3: reglas de negocio (código)
    def _reglas_del_tipo(self, tipo: TipoDoc, c: dict) -> list[Hallazgo]:
        """Deterministas, probadas con pruebas unitarias, auditables.
        Un requisito de admisión NO se evalúa con un LLM.
        Un dato ilegible nunca tumba el proceso: se convierte en hallazgo."""
        out: list[Hallazgo] = []
        hoy = date.today()

        if tipo is TipoDoc.CEDULA:
            num = re.sub(r"\D", "", str(c.get("numero_documento", "")))
            if not 6 <= len(num) <= 10:
                out.append(Hallazgo("CEDULA_FORMATO", "critico",
                                    "El número de cédula no se pudo leer o no tiene "
                                    "un formato válido.",
                                    peso=60, evidencia={"leido": num}))
            if c.get("fecha_nacimiento"):
                f = _fecha(c["fecha_nacimiento"])
                if f is None:
                    out.append(_fecha_ilegible("fecha_nacimiento", c["fecha_nacimiento"]))
                else:
                    edad = _edad(f, hoy)
                    if not 16 <= edad <= 100:
                        out.append(Hallazgo("EDAD_IMPROBABLE", "critico",
                                            "La fecha de nacimiento no es coherente.",
                                            peso=70, evidencia={"edad": edad}))

        elif tipo in (TipoDoc.ACTA_GRADO, TipoDoc.DIPLOMA):
            if not c.get("institucion"):
                out.append(Hallazgo("SIN_INSTITUCION", "critico",
                                    "No se identifica la institución que expide el título.",
                                    peso=60))
            if c.get("fecha_grado"):
                f = _fecha(c["fecha_grado"])
                if f is None:
                    out.append(_fecha_ilegible("fecha_grado", c["fecha_grado"]))
                elif f > hoy:
                    out.append(Hallazgo("FECHA_GRADO_FUTURA", "critico",
                                        "La fecha de grado es posterior a hoy.", peso=80,
                                        evidencia={"fecha": f.isoformat()}))
            # CAPA 4: verificación contra fuente autoritativa.
            # Esta es la única evidencia real de autenticidad del sistema.
            if (snies := c.get("codigo_snies")):
                if not self.sia.verificar_programa_snies(snies, c.get("institucion")):
                    out.append(Hallazgo(
                        "SNIES_NO_VERIFICADO", "advertencia",
                        "No se pudo verificar el programa en el registro SNIES.",
                        peso=30, evidencia={"snies": snies}))
            else:
                out.append(Hallazgo("SIN_CODIGO_SNIES", "info",
                                    "El documento no incluye código SNIES.", peso=10))

        elif tipo is TipoDoc.TRANSCRIPT:
            prom = _numero(c.get("promedio_acumulado"))
            escala = _numero(c.get("escala")) or 5.0
            if prom is None:
                out.append(Hallazgo("SIN_PROMEDIO", "advertencia",
                                    "No se identifica el promedio acumulado.", peso=25))
            elif not 0 <= prom <= escala:
                out.append(Hallazgo("PROMEDIO_FUERA_ESCALA", "critico",
                                    "El promedio está fuera de la escala del documento.",
                                    peso=60, evidencia={"promedio": prom, "escala": escala}))
            cr = _numero(c.get("creditos_aprobados"))
            if cr is not None and cr < 100:
                out.append(Hallazgo("CREDITOS_INSUFICIENTES", "advertencia",
                                    "Los créditos aprobados parecen insuficientes "
                                    "para un título profesional.",
                                    peso=20, evidencia={"creditos": cr}))
        return out

    # ==================== CAPA 5: coherencia cruzada entre documentos y CRM
    def _cruzar(self, docs: list[ResultadoDoc], solicitud_id: str):
        """La capa más útil de todas y la que un humano hace peor: comparar el
        mismo dato entre cuatro documentos y el formulario."""
        perfil = self.crm.obtener_solicitud(solicitud_id) or {}
        por_tipo = {d.tipo: d for d in docs}
        ced = por_tipo.get(TipoDoc.CEDULA)
        acta = por_tipo.get(TipoDoc.ACTA_GRADO)

        nombres = {}
        if ced:
            nombres["cédula"] = normalizar_nombre(ced.campos.get("nombre_completo"))
        if acta:
            nombres["acta de grado"] = normalizar_nombre(acta.campos.get("nombre_graduado"))
        nombres["formulario"] = normalizar_nombre(perfil.get("nombre_completo"))

        # La referencia es la cédula; sin cédula, el formulario.
        ref_origen = "cédula" if nombres.get("cédula") else "formulario"
        base = nombres.get(ref_origen, "")
        if base:
            for origen, valor in nombres.items():
                if not valor or origen == ref_origen:
                    continue
                sim = similitud_nombres(base, valor)
                if sim < UMBRAL_SIMILITUD_NOMBRE:
                    yield Hallazgo(
                        "NOMBRE_NO_COINCIDE", "critico",
                        f"El nombre en {origen} no coincide con el de {ref_origen}.",
                        peso=55, evidencia={ref_origen: base, origen: valor,
                                            "similitud": round(sim, 2)})

        if ced:
            doc_ced = re.sub(r"\D", "", str(ced.campos.get("numero_documento", "")))
            doc_form = re.sub(r"\D", "", str(perfil.get("numero_documento", "")))
            if doc_ced and doc_form and doc_ced != doc_form:
                yield Hallazgo(
                    "DOCUMENTO_NO_COINCIDE", "critico",
                    "El número de documento no coincide con el del formulario.",
                    peso=80, evidencia={"cedula": doc_ced, "formulario": doc_form})

        # Duplicado global: mismo hash ya cargado en OTRA solicitud.
        for d in docs:
            previa = self.storage.buscar_por_hash(d.hash_archivo)
            if previa and previa.get("solicitud_id") != solicitud_id:
                yield Hallazgo(
                    "ARCHIVO_DUPLICADO", "critico",
                    "Este archivo idéntico ya fue cargado en otra solicitud.",
                    peso=70, evidencia={"solicitud_previa": previa.get("solicitud_id")},
                    documento=d.nombre_archivo)

    # ------------------------------------------------------------------ score
    def _faltantes(self, docs, programa_tipo) -> list[str]:
        presentes = {d.tipo for d in docs}
        return [t.value for t in DOCS_REQUERIDOS.get(programa_tipo, [])
                if t not in presentes]

    @staticmethod
    def _score(docs: list[ResultadoDoc], cruzados: list[Hallazgo]) -> int:
        """100 = limpio. Cada hallazgo resta su peso; la firma digital suma."""
        penal = sum(h.peso for d in docs for h in d.hallazgos)
        penal += sum(h.peso for h in cruzados)
        return max(0, min(100, 100 - penal))

    def _redactar(self, res: ResultadoSolicitud, url_carga: str) -> str:
        """Mensaje al aspirante. Nunca acusa: describe qué revisar y cómo
        corregirlo. La diferencia entre 'documento sospechoso' y 'el escaneo
        está borroso' es la diferencia entre un reclamo y una corrección.
        Solo recibe hallazgos corregibles; si el LLM falla, se usa una plantilla."""
        problemas = []
        for h in res.hallazgos:
            if h.corregible and h.severidad != "info":
                donde = f" (archivo {h.documento})" if h.documento else ""
                problemas.append(h.mensaje + donde)
        enlace = url_carga or "[enlace de carga]"
        plantilla = ("Hola. Revisamos tu documentación para ESIC Medellín y necesitamos "
                     "que corrijas lo siguiente:\n- " + "\n- ".join(problemas) +
                     f"\n\nPuedes cargar los documentos aquí: {enlace}\n"
                     "Gracias por tu paciencia.")
        try:
            r = self.llm.completar(
                tarea=Tarea.EXTRACCION,
                mensajes=[
                    {"role": "system", "content":
                     "Redacta un correo breve y amable en español de Colombia para un "
                     "aspirante de ESIC Medellín. Explica qué debe corregir en su "
                     "documentación y cómo hacerlo. Máximo 120 palabras. Tutea. "
                     "NUNCA insinúes fraude, falsificación ni mala intención: describe "
                     "solo qué falta o qué no se pudo leer. Usa exactamente el enlace "
                     "de carga que se te da, sin inventar otro. No uses emojis. "
                     "No incluyas asunto ni firma con nombre propio."},
                    {"role": "user", "content": json.dumps(
                        {"problemas": problemas, "enlace_de_carga": enlace},
                        ensure_ascii=False)}],
                conv_id=f"doc-{res.solicitud_id}")
            texto = (r.texto or "").strip()
            return texto if texto and enlace in texto else plantilla
        except Exception:  # noqa: BLE001 - el correo no puede bloquear el flujo
            log.warning("no se pudo redactar con LLM; se usa plantilla")
            return plantilla


# ---------------------------------------------------------------- utilidades
def normalizar_nombre(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").upper())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


def similitud_nombres(a: str, b: str) -> float:
    """Similitud insensible al orden de las palabras. La cédula colombiana pone
    los apellidos primero y el formulario suele poner los nombres primero:
    'GOMEZ RESTREPO MARIA' y 'MARIA GOMEZ RESTREPO' son la misma persona."""
    ta, tb = " ".join(sorted(a.split())), " ".join(sorted(b.split()))
    return SequenceMatcher(None, ta, tb).ratio()


def _fecha(v: Any) -> date | None:
    if isinstance(v, date):
        return v
    t = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def _edad(nacimiento: date, hoy: date) -> int:
    return hoy.year - nacimiento.year - (
        (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def _numero(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def _fecha_ilegible(campo: str, valor: Any) -> Hallazgo:
    return Hallazgo("FECHA_ILEGIBLE", "advertencia",
                    "Una fecha del documento no se pudo leer con claridad.",
                    peso=15, evidencia={"campo": campo, "leido": str(valor)})
