# Código acompañante · Caso Práctico Fábrica de IA · ESIC Medellín

**Henry Taborda** · Python 3.9+ · sin dependencias externas para el demo y las pruebas

| Recurso | Enlace |
|---|---|
| Demo desplegado | https://agora-esic.vercel.app |
| Demo extendido (traza, validador, ROI, video, motor Claude; pide sesión en claude.ai o abra `../demo_web/index.html`) | https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7 |
| Video demostrativo (narrado) | https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4 · `../video/Demo_Fabrica_IA_Henry_Taborda.mp4` |
| Repositorio | https://github.com/HenryStark866/Agora-demo-esic |

**Guía paso a paso (web, consola y modelo real):** [GUIA_DEMO.md](GUIA_DEMO.md)

## Ejecutar en 30 segundos

```bash
python demo.py                 # Escenarios 1 y 2 de principio a fin (motor simulado)
python modelo_roi.py           # Modelo de impacto y ROI (todas las cifras del Documento 4)
python -m unittest discover -s pruebas -t .   # 42 pruebas
```

En Linux o macOS use `python3` si `python` no apunta a la versión 3.

`demo.py` ejecuta **el mismo orquestador y el mismo validador** que irían a
producción. Lo simulado son los servicios que los rodean (índice de búsqueda,
ERP, CRM, Document Intelligence) y, en el modo por defecto, el modelo de
lenguaje. Todos los datos del demo son ficticios.

### Con un modelo de lenguaje real

El gateway (`comun/llm_gateway.py`) cambia de proveedor por configuración:

```bash
# Gemini (API compatible con OpenAI)
$env:GEMINI_API_KEY="su_clave"          # PowerShell  (set ... en CMD, export ... en Linux/macOS)
python demo.py --proveedor gemini

# Cualquier API compatible con OpenAI: Groq, OpenRouter, vLLM, Ollama...
$env:LLM_BASE_URL="https://api.groq.com/openai/v1"
$env:LLM_API_KEY="su_clave"
$env:LLM_MODELO="nombre-del-modelo"
python demo.py --proveedor compatible
```

Las claves se leen de variables de entorno; ninguna está escrita en el código.

## Estructura

```
codigo/
├── demo.py                               ← EJECUTABLE: ejemplo de funcionamiento
├── modelo_roi.py                         ← EJECUTABLE: modelo de impacto y ROI
├── comun/
│   ├── llm_gateway.py                    Capa de abstracción de modelos (ADR-05)
│   └── cliente_http.py                   Cliente compatible con OpenAI, sin dependencias
├── escenario1_chatbot/
│   ├── prompts.py                        Los 4 prompts de sistema, versionados
│   └── orquestador.py                    Pipeline RAG de 8 pasos + derivación
├── escenario2_documentos/
│   ├── validador.py                      5 capas de validación + score de riesgo
│   └── n8n_flujo_validacion.json         Flujo de 20 nodos, importable en n8n
├── demo/                                 Datos ficticios y servicios simulados
└── pruebas/                              42 pruebas unitarias (unittest)
```

## Dónde mirar primero

| Si le interesa… | Abra |
|---|---|
| Cómo se evita que el bot invente precios | `escenario1_chatbot/orquestador.py` → `TOOLS`, `_generar()` y `_verificar()` |
| Cómo se impide que un aspirante lea contenido interno | `orquestador.py` → `_recuperar()` y `AUDIENCIAS_VALIDAS` |
| Cómo se controla el costo de inferencia | `comun/llm_gateway.py` → catálogos, `_verificar_presupuesto()` |
| Cómo se decide aprobar un documento | `escenario2_documentos/validador.py` → `_score()`, `_decidir()` y las 5 capas |
| Dónde vive la lógica y dónde el flujo | `n8n_flujo_validacion.json` → nodos 6, 11 y 18 |
| Si los números del ROI se sostienen | `modelo_roi.py`, secciones 6 y 7 (sensibilidad) |

## Notas para importar el flujo en n8n

- Variables de entorno: `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` y `NODE_FUNCTION_ALLOW_BUILTIN=crypto`.
- Las credenciales (Header Auth, OAuth2 de Entra ID, Outlook, Teams, Postgres) se asignan al importar.
- La lista completa de variables que usa el flujo está en `meta.variables_de_entorno`.
