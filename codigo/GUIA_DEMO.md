# Guía paso a paso para probar el demo

**Caso práctico Fábrica de IA y Automatización · ESIC Medellín · Henry Taborda**

Hay tres formas de probar la solución. La primera no requiere instalar nada.

| Opción | Qué necesita | Tiempo |
|---|---|---|
| A. Demo web | Un navegador | 1 minuto |
| B. Demo por consola | Python 3.9 o superior | 3 minutos |
| C. Consola con un modelo real | Python y una clave de API con saldo | 5 minutos |

Todos los programas, precios, fechas, cifras y personas del demo son **ficticios**.

---

## A. Demo web (recomendado)

Hay dos demos en línea:

- **Demo desplegado — https://agora-esic.vercel.app**: el chatbot del Escenario 1 y la validación del Escenario 2, con backend en Supabase Edge Functions. Abre directamente, sin cuenta.
- **Demo extendido — https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7** (pide iniciar sesión en claude.ai): agrega la traza detallada de los 8 pasos, la validación documental editable, el modelo de ROI interactivo, el video narrado y el motor con un modelo real. Los pasos siguientes se refieren a este demo.

**Sin cuenta de Claude:** abra `demo_web/index.html` de la entrega con doble clic: es la misma página, funciona sin conexión con el motor simulado y reproduce el video desde la carpeta `video/`.

1. Abra el enlace: **https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7**
2. La página abre en la pestaña **E1 · Chatbot con RAG**, con el motor **Simulado** activo.
3. Pulse cualquiera de las preguntas de ejemplo, debajo de la conversación. Por ejemplo, *Egresado: descuento, empleabilidad y fechas*.
4. Observe el panel **Traza del pipeline**. Los 8 pasos se encienden en orden: seguridad, router, caché, recuperación (con los fragmentos excluidos por audiencia, sensibilidad o vigencia), datos en vivo, generación, verificación y salida.
5. Pruebe también *Sin evidencia*, *Contenido interno* e *Inyección de prompt*. En esos casos el sistema no responde con datos: deriva o bloquea, y la traza muestra por qué.
6. Pestaña **E2 · Validación documental**:
   - Elija uno de los cuatro casos.
   - Cambie cualquier dato: el número del formulario, la confianza del OCR o las casillas de firma, editor de imágenes, duplicado o documento faltante.
   - El score, la decisión y el correo al aspirante se recalculan al instante.
7. Pestaña **ROI · Modelo de impacto**:
   - Mueva los controles de consultas por día, deflexión, costo por interacción y aumento de conversión.
   - Con los valores iniciales, la página reproduce las cifras del Documento 4: 70,6 %, ROI del año 2 de 38,4 % y punto de equilibrio de 238 consultas.
8. Pestaña **Video**: el recorrido narrado de 6 minutos. También está en https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4 y en `video/` de la entrega.

### Activar el motor con un modelo real (Claude)

La página puede usar un modelo de lenguaje real **sin claves ni costo para el autor**. Usa la cuenta de Claude de quien la abre.

1. Inicie sesión en **https://claude.ai** con cualquier cuenta. El plan gratuito sirve, dentro de sus límites de uso.
2. Abra el enlace del demo en ese mismo navegador.
3. Espere unos segundos a que se habilite el botón **Claude (real)**, arriba a la derecha, y púlselo. El indicador cambia a *modelo real · usa tu plan de Claude*.
4. Envíe una pregunta. La primera vez, claude.ai pide **autorizar** que la página use Claude. Pulse *Permitir*.
5. El router, la generación con llamadas a herramientas y la verificación usan ahora un modelo real, con los mismos prompts del código. Las respuestas tardan entre 5 y 40 segundos. La recuperación y los datos en vivo siguen siendo los ficticios del demo.
6. En la pestaña E2, con el motor real, el correo al aspirante lo redacta Claude.

**Si el botón Claude (real) sigue deshabilitado:** la página se abrió sin sesión de claude.ai o fuera del visor de claude.ai. El motor simulado funciona igual.
**Si aparece "No se autorizó el uso de Claude":** se rechazó el permiso. Recargue la página para que lo vuelva a pedir.
**Si aparece "Se alcanzó el límite de uso":** la cuenta llegó a su límite. Espere unos minutos o use el motor simulado.

---

## B. Demo por consola (sin claves)

### Windows

1. Instale Python 3.9 o superior desde **https://www.python.org/downloads/**. En el instalador, marque **"Add python.exe to PATH"**.
2. Descomprima el ZIP de la entrega.
3. Abra la carpeta `codigo`. Haga clic derecho en un espacio vacío y elija **Abrir en Terminal**. En Windows 10: Shift + clic derecho → *Abrir la ventana de PowerShell aquí*.
4. Compruebe la versión:
   ```
   python --version
   ```
5. Ejecute el demo completo (Escenarios 1 y 2):
   ```
   python demo.py
   ```
6. Otras opciones:
   ```
   python demo.py --escenario 1      # solo el chatbot (9 casos)
   python demo.py --escenario 2      # solo la validación documental (4 solicitudes)
   python demo.py --pausa            # se detiene entre casos; avance con Enter
   python modelo_roi.py              # modelo de impacto y ROI
   python -m unittest discover -s pruebas -t .     # 42 pruebas
   ```

### macOS o Linux

Los mismos pasos, usando `python3` en lugar de `python`.

No hace falta instalar ninguna librería: todo usa la biblioteca estándar de Python.

---

## C. Consola con un modelo real

El orquestador cambia de proveedor por configuración. En este modo, el router, la generación y la verificación los hace el modelo real. El índice, los datos en vivo y los documentos siguen siendo simulados.

### Con Gemini

1. Consiga una clave en **https://aistudio.google.com** → *Get API key*. El proyecto de la clave debe tener **saldo** o el **nivel gratuito** activo.
2. En la terminal, dentro de `codigo`, defina la clave solo para esa sesión:
   - PowerShell: `$env:GEMINI_API_KEY="su_clave"`
   - CMD: `set GEMINI_API_KEY=su_clave`
   - macOS / Linux: `export GEMINI_API_KEY="su_clave"`
3. Ejecute:
   ```
   python demo.py --proveedor gemini
   ```
4. El demo verifica primero la conexión. Si algo falla, lo dice con claridad y sugiere el modo simulado.

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| `429 … prepayment credits are depleted` | El proyecto no tiene saldo | Recargar en AI Studio → *Billing*, o crear la clave en un proyecto sin facturación (nivel gratuito) |
| `404 … model … not found` | El modelo no está disponible para esa cuenta | Definir otro modelo, por ejemplo `$env:GEMINI_MODELO_RESPUESTA="gemini-flash-latest"` |
| `401` / `403` | Clave inválida o sin permisos | Revisar la clave |

Modelos por defecto: `gemini-3.5-flash-lite` (clasificación y verificación), `gemini-3.6-flash` (respuesta y redacción) y `gemini-3.1-pro-preview` (razonamiento). Cada uno se puede cambiar con las variables `GEMINI_MODELO_CLASIFICACION`, `GEMINI_MODELO_RESPUESTA`, `GEMINI_MODELO_RAZONAMIENTO` y `GEMINI_MODELO_EXTRACCION`.

### Con cualquier API compatible con OpenAI (Groq, OpenRouter, vLLM, Ollama…)

```
$env:LLM_BASE_URL="https://api.groq.com/openai/v1"     # o https://openrouter.ai/api/v1
$env:LLM_API_KEY="su_clave"
$env:LLM_MODELO="nombre-del-modelo"
python demo.py --proveedor compatible
```

**Seguridad:** las claves se leen de variables de entorno y no se guardan en ningún archivo. No escriba una clave dentro del código ni la comparta en documentos.

**Qué esperar con un modelo real:** las respuestas cambian de una ejecución a otra, y el verificador puede derivar a un asesor más casos que el motor simulado. Es el comportamiento buscado: el sistema prefiere no responder antes que responder sin evidencia. El caso 8, que fuerza una alucinación, solo la produce en el motor simulado.

---

## Qué mirar en el código

| Pregunta | Archivo |
|---|---|
| ¿Cómo se evita que el bot invente precios? | `escenario1_chatbot/orquestador.py` → `TOOLS`, `_generar()`, `_verificar()` |
| ¿Cómo se impide leer contenido interno? | `orquestador.py` → `_recuperar()` y `AUDIENCIAS_VALIDAS` |
| ¿Cómo se cambia de proveedor de modelos? | `comun/llm_gateway.py` → `CATALOGOS` |
| ¿Cómo se decide sobre un documento? | `escenario2_documentos/validador.py` → `_score()` y `_decidir()` |
| ¿Dónde vive el flujo? | `escenario2_documentos/n8n_flujo_validacion.json` (20 nodos) |
