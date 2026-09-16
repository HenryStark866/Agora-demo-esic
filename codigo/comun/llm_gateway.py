# -*- coding: utf-8 -*-
"""
llm_gateway.py — Capa de abstracción de modelos (ADR-05)

Toda llamada a un LLM en la Fábrica de IA pasa por aquí. Nunca se importa el SDK
de un proveedor desde la lógica de negocio.

Qué resuelve:
  1. Portabilidad      — cambiar de proveedor es configuración, no refactor.
                         Hay dos catálogos: Azure OpenAI (producción) y Gemini
                         (usado en el demo). El resto del código no cambia.
  2. Enrutamiento      — la tarea elige el modelo, no el desarrollador de turno.
  3. Control de costo  — presupuesto duro por conversación + caché exacta de
                         respuestas. (La caché SEMÁNTICA vive en el orquestador,
                         porque depende de la audiencia y del dato vivo.)
  4. Resiliencia       — reintentos con espera exponencial ante errores
                         transitorios (429, 5xx, timeouts).
  5. Observabilidad    — una sola traza para todo el tráfico de IA.

Dependencias en producción: openai>=1.40 (cliente AzureOpenAI), redis,
azure-identity. El demo usa comun/cliente_http.py, que no tiene dependencias.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("fabrica.llm")


# --------------------------------------------------------------------------
# Catálogos de modelos: la única parte que cambia al migrar de proveedor
# --------------------------------------------------------------------------
class Tarea(str, Enum):
    CLASIFICACION = "clasificacion"   # router de intención, verificación, etiquetado
    RESPUESTA     = "respuesta"       # generación con RAG (80% del tráfico)
    RAZONAMIENTO  = "razonamiento"    # consultas multi-salto, casos límite
    EXTRACCION    = "extraccion"      # datos estructurados, redacción de correos
    EMBEDDING     = "embedding"


# temp=None -> no se envía el parámetro. Los modelos de razonamiento de la
# familia GPT-5.x en Azure no aceptan `temperature`; se controla con
# `reasoning_effort`. La coherencia no se garantiza con la temperatura sino con
# grounding + verificación (orquestador, pasos 6 y 7).
RUTEO_AZURE: dict[Tarea, dict[str, Any]] = {
    Tarea.CLASIFICACION: {"modelo": "gpt-5.4-nano", "temp": None, "max_out": 512,
                          "esfuerzo": "low"},
    Tarea.RESPUESTA:     {"modelo": "gpt-5.4-mini", "temp": None, "max_out": 1200,
                          "esfuerzo": "low"},
    Tarea.RAZONAMIENTO:  {"modelo": "gpt-5.4",      "temp": None, "max_out": 4000,
                          "esfuerzo": "medium"},
    Tarea.EXTRACCION:    {"modelo": "gpt-5.4-mini", "temp": None, "max_out": 1500,
                          "esfuerzo": "low"},
    Tarea.EMBEDDING:     {"modelo": "text-embedding-3-large"},
}

# Gemini por su endpoint compatible con OpenAI. Los modelos se pueden
# sobrescribir con variables de entorno sin tocar el código.
RUTEO_GEMINI: dict[Tarea, dict[str, Any]] = {
    Tarea.CLASIFICACION: {"modelo": os.getenv("GEMINI_MODELO_CLASIFICACION", "gemini-3.5-flash-lite"),
                          "temp": None, "max_out": 4096, "esfuerzo": "low", "param_max": "max_tokens"},
    Tarea.RESPUESTA:     {"modelo": os.getenv("GEMINI_MODELO_RESPUESTA", "gemini-3.6-flash"),
                          "temp": None, "max_out": 8192, "esfuerzo": "low", "param_max": "max_tokens"},
    Tarea.RAZONAMIENTO:  {"modelo": os.getenv("GEMINI_MODELO_RAZONAMIENTO", "gemini-3.1-pro-preview"),
                          "temp": None, "max_out": 8192, "esfuerzo": "high", "param_max": "max_tokens"},
    Tarea.EXTRACCION:    {"modelo": os.getenv("GEMINI_MODELO_EXTRACCION", "gemini-3.6-flash"),
                          "temp": None, "max_out": 8192, "esfuerzo": "low", "param_max": "max_tokens"},
    Tarea.EMBEDDING:     {"modelo": os.getenv("GEMINI_MODELO_EMBEDDING", "gemini-embedding-001"),
                          "dimensiones": 768},
}

# Cualquier API compatible con OpenAI (Groq, OpenRouter, vLLM, Ollama...):
# un solo modelo para todas las tareas, definido por variable de entorno.
_MODELO_COMPATIBLE = os.getenv("LLM_MODELO", "modelo-no-configurado")
RUTEO_COMPATIBLE: dict[Tarea, dict[str, Any]] = {
    t: {"modelo": _MODELO_COMPATIBLE, "temp": 0.2, "max_out": 2048, "param_max": "max_tokens"}
    for t in (Tarea.CLASIFICACION, Tarea.RESPUESTA, Tarea.RAZONAMIENTO, Tarea.EXTRACCION)
}
RUTEO_COMPATIBLE[Tarea.EMBEDDING] = {"modelo": os.getenv("LLM_MODELO_EMBEDDING", "")}

CATALOGOS = {"azure": RUTEO_AZURE, "gemini": RUTEO_GEMINI,
             "compatible": RUTEO_COMPATIBLE}

# Compatibilidad con la versión anterior del módulo.
RUTEO = RUTEO_AZURE

# Presupuesto duro. Una conversación que lo supere se deriva a un humano:
# es más barato y más honesto que dejarla escalar sin control.
PRESUPUESTO_CONVERSACION_USD = 0.25

REINTENTOS_MAX = 3
ESPERA_BASE_S  = 0.8


@dataclass
class Uso:
    tokens_in: int = 0
    tokens_out: int = 0
    costo_usd: float = 0.0
    latencia_ms: int = 0
    modelo: str = ""
    cache_hit: bool = False


@dataclass
class Respuesta:
    texto: str
    uso: Uso
    tool_calls: list[dict] = field(default_factory=list)
    raw: Any = None


class PresupuestoExcedido(Exception):
    """La conversación agotó su presupuesto. El orquestador debe derivar a humano."""


class ErrorProveedor(Exception):
    """Error del proveedor de modelos que no se resolvió con reintentos."""


def _es_transitorio(e: Exception) -> bool:
    estado = getattr(e, "status_code", None) or getattr(e, "status", None)
    if estado is not None:
        return int(estado) in (408, 409, 429, 500, 502, 503, 504)
    return isinstance(e, (TimeoutError, ConnectionError))


class LLMGateway:
    def __init__(self, cliente, cache=None, precios: dict | None = None,
                 proveedor: str = "azure", presupuesto_usd: float | None = None):
        if proveedor not in CATALOGOS:
            raise ValueError(f"proveedor desconocido: {proveedor}")
        self._c = cliente                 # AzureOpenAI(...) o cliente compatible
        self._cache = cache               # cliente Redis (get / setex), opcional
        self.proveedor = proveedor
        self.ruteo = CATALOGOS[proveedor]
        self.presupuesto = (PRESUPUESTO_CONVERSACION_USD
                            if presupuesto_usd is None else presupuesto_usd)
        # USD por 1.000 tokens. Se carga desde configuración para no quemar
        # precios en el código; se valida contra la API de precios cada mes.
        self._precios = precios or {}
        self._sin_precio_avisado: set[str] = set()
        # LIMITACIÓN CONOCIDA: contador en memoria del proceso. En Container Apps
        # con varias réplicas cada una lleva su propio conteo. En producción va a
        # Redis con INCRBYFLOAT sobre la clave de la conversación (atómico y
        # compartido); el cambio es de ~6 líneas en _cobrar() y gasto().
        self._gasto: dict[str, float] = {}

    # ---------------------------------------------------------------- costo
    def _costo(self, modelo: str, tin: int, tout: int) -> float:
        p = self._precios.get(modelo)
        if p is None:
            if modelo not in self._sin_precio_avisado:
                # Sin precio, el presupuesto no protege nada: se avisa una vez.
                log.warning("modelo sin precio configurado: %s", modelo)
                self._sin_precio_avisado.add(modelo)
            return 0.0
        return (tin / 1000) * p["in"] + (tout / 1000) * p["out"]

    def gasto(self, conv_id: str) -> float:
        return self._gasto.get(conv_id, 0.0)

    def _verificar_presupuesto(self, conv_id: str) -> None:
        # Se verifica ANTES de llamar: no se paga una llamada cuya respuesta
        # se va a descartar por falta de presupuesto.
        if self.gasto(conv_id) >= self.presupuesto:
            raise PresupuestoExcedido(
                f"conversación {conv_id}: USD {self.gasto(conv_id):.4f} "
                f">= {self.presupuesto}")

    def _cobrar(self, conv_id: str, costo: float) -> None:
        self._gasto[conv_id] = self.gasto(conv_id) + costo

    # --------------------------------------------------------------- caché
    def _clave_cache(self, tarea: Tarea, modelo: str, mensajes: list[dict],
                     forzar_json: bool) -> str:
        # El modelo y el formato van en la clave: cambiar de modelo invalida
        # la caché en vez de servir respuestas de otro modelo.
        semilla = json.dumps([modelo, forzar_json, mensajes],
                             sort_keys=True, ensure_ascii=False)
        return f"llm:{tarea.value}:{hashlib.sha256(semilla.encode()).hexdigest()}"

    # ----------------------------------------------------------- reintentos
    def _con_reintentos(self, fn, **kwargs):
        for intento in range(1, REINTENTOS_MAX + 1):
            try:
                return fn(**kwargs)
            except Exception as e:  # noqa: BLE001 - se reclasifica abajo
                if not _es_transitorio(e) or intento == REINTENTOS_MAX:
                    raise ErrorProveedor(f"{type(e).__name__}: {e}") from e
                espera = ESPERA_BASE_S * (2 ** (intento - 1)) + random.uniform(0, 0.3)
                log.warning("error transitorio (%s), reintento %d en %.1fs",
                            e, intento, espera)
                time.sleep(espera)

    # -------------------------------------------------------------- pública
    def completar(
        self,
        tarea: Tarea,
        mensajes: list[dict],
        conv_id: str,
        tools: list[dict] | None = None,
        forzar_json: bool = False,
        usar_cache: bool = True,
    ) -> Respuesta:
        cfg = self.ruteo[tarea]
        modelo = cfg["modelo"]
        t0 = time.perf_counter()

        cacheable = usar_cache and self._cache is not None and not tools
        if cacheable:
            k = self._clave_cache(tarea, modelo, mensajes, forzar_json)
            hit = self._cache.get(k)
            if hit:
                d = json.loads(hit)
                return Respuesta(
                    texto=d["texto"],
                    uso=Uso(modelo=modelo, cache_hit=True,
                            latencia_ms=int((time.perf_counter() - t0) * 1000)))

        self._verificar_presupuesto(conv_id)

        kwargs: dict[str, Any] = {
            "model": modelo,
            "messages": mensajes,
        }
        # Azure/OpenAI usan max_completion_tokens; otros proveedores compatibles, max_tokens.
        kwargs[cfg.get("param_max", "max_completion_tokens")] = cfg["max_out"]
        if cfg.get("temp") is not None:
            kwargs["temperature"] = cfg["temp"]
        if cfg.get("esfuerzo"):
            kwargs["reasoning_effort"] = cfg["esfuerzo"]
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if forzar_json:
            kwargs["response_format"] = {"type": "json_object"}

        r = self._con_reintentos(self._c.chat.completions.create, **kwargs)

        tin = getattr(r.usage, "prompt_tokens", 0) or 0
        tout = getattr(r.usage, "completion_tokens", 0) or 0
        costo = self._costo(modelo, tin, tout)
        self._cobrar(conv_id, costo)

        uso = Uso(tin, tout, costo,
                  int((time.perf_counter() - t0) * 1000), modelo)
        msg = r.choices[0].message
        resp = Respuesta(
            texto=msg.content or "",
            uso=uso,
            tool_calls=[tc.model_dump() for tc in (msg.tool_calls or [])],
            raw=r,
        )

        if cacheable and resp.texto:
            self._cache.setex(k, 3600,
                              json.dumps({"texto": resp.texto}, ensure_ascii=False))

        log.info("llm", extra={"conv": conv_id, "tarea": tarea.value,
                               "modelo": modelo, "tin": tin, "tout": tout,
                               "usd": round(costo, 5), "ms": uso.latencia_ms})
        return resp

    def embeber(self, textos: list[str]) -> list[list[float]]:
        cfg = self.ruteo[Tarea.EMBEDDING]
        kwargs: dict[str, Any] = {"model": cfg["modelo"], "input": textos}
        if cfg.get("dimensiones"):
            kwargs["dimensions"] = cfg["dimensiones"]
        r = self._con_reintentos(self._c.embeddings.create, **kwargs)
        return [d.embedding for d in r.data]
