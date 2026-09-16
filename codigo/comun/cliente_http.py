# -*- coding: utf-8 -*-
"""
cliente_http.py — Cliente mínimo compatible con la API de OpenAI, sin dependencias.

Sirve para cualquier proveedor que exponga el contrato /chat/completions y
/embeddings (Azure OpenAI v1, Gemini, modelos abiertos con vLLM). El gateway lo
usa exactamente igual que al SDK oficial: `cliente.chat.completions.create(...)`.

La clave NUNCA se escribe en el código: se lee de una variable de entorno.

    set GEMINI_API_KEY=...        (Windows)
    export GEMINI_API_KEY=...     (Linux / macOS)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Any

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"


class ErrorHTTP(Exception):
    def __init__(self, status: int, cuerpo: str):
        self.status_code = status
        super().__init__(f"HTTP {status}: {_resumen_error(cuerpo)}")


def _resumen_error(cuerpo: str) -> str:
    try:
        d = json.loads(cuerpo)
        d = d[0] if isinstance(d, list) else d
        return d.get("error", {}).get("message", cuerpo)[:300]
    except Exception:  # noqa: BLE001
        return cuerpo[:300]


class _Obj(SimpleNamespace):
    """Objeto con acceso por atributo y `model_dump()`, como los del SDK."""

    def model_dump(self) -> dict:
        return _a_dict(self)


def _a_obj(x: Any) -> Any:
    if isinstance(x, dict):
        return _Obj(**{k: _a_obj(v) for k, v in x.items()})
    if isinstance(x, list):
        return [_a_obj(v) for v in x]
    return x


def _a_dict(x: Any) -> Any:
    if isinstance(x, SimpleNamespace):
        return {k: _a_dict(v) for k, v in vars(x).items()}
    if isinstance(x, list):
        return [_a_dict(v) for v in x]
    return x


class ClienteCompatibleOpenAI:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0):
        if not api_key:
            raise ValueError("falta la clave de API")
        self._base = base_url.rstrip("/") + "/"
        self._key = api_key
        self._timeout = timeout
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.embeddings = SimpleNamespace(create=self._embeddings)

    def _post(self, ruta: str, cuerpo: dict) -> dict:
        req = urllib.request.Request(
            self._base + ruta,
            data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._key}",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                d = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ErrorHTTP(e.code, e.read().decode("utf-8", "replace")) from None
        except urllib.error.URLError as e:
            raise ConnectionError(str(e.reason)) from None
        return d[0] if isinstance(d, list) else d

    def _chat(self, **kwargs) -> Any:
        d = self._post("chat/completions", kwargs)
        d.setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0})
        for c in d.get("choices", []):
            c.setdefault("message", {}).setdefault("tool_calls", None)
            c["message"].setdefault("content", None)
        return _a_obj(d)

    def _embeddings(self, **kwargs) -> Any:
        return _a_obj(self._post("embeddings", kwargs))


def cliente_gemini(api_key: str | None = None) -> ClienteCompatibleOpenAI:
    clave = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not clave:
        raise RuntimeError(
            "No hay clave de Gemini. Defina la variable de entorno GEMINI_API_KEY "
            "o ejecute el demo con --proveedor simulado.")
    return ClienteCompatibleOpenAI(URL_GEMINI, clave)


def cliente_compatible() -> ClienteCompatibleOpenAI:
    """Cualquier proveedor con API compatible con OpenAI.
    LLM_BASE_URL (p. ej. https://api.groq.com/openai/v1), LLM_API_KEY, LLM_MODELO."""
    url, clave = os.getenv("LLM_BASE_URL"), os.getenv("LLM_API_KEY")
    if not (url and clave and os.getenv("LLM_MODELO")):
        raise RuntimeError("Defina LLM_BASE_URL, LLM_API_KEY y LLM_MODELO.")
    return ClienteCompatibleOpenAI(url, clave)


class ClienteMixto:
    """Chat en el proveedor remoto; embeddings locales. Útil cuando el
    proveedor no ofrece embeddings o para no depender de ellos en un demo."""

    def __init__(self, remoto, local):
        self.chat = remoto.chat
        self.embeddings = local.embeddings
