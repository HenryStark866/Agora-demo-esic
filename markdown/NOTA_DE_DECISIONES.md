# Nota de decisiones

**Henry Taborda** · Caso Práctico Fábrica de IA y Automatización · ESIC Medellín
15 de septiembre de 2026

**Demo desplegado:** [agora-esic.vercel.app](https://agora-esic.vercel.app) · **Demo extendido** (sesión claude.ai): [enlace](https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7) · **Video:** [GitHub](https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4) · **Repositorio:** [HenryStark866/Agora-demo-esic](https://github.com/HenryStark866/Agora-demo-esic)

---

Antes de los documentos, las seis decisiones que tomé y por qué. Si algo de la
entrega les parece discutible, probablemente esté aquí.

**1. Elegí los escenarios 1 y 2 a profundidad, y el 3 a nivel de diseño.**
El caso pedía al menos dos. Tomé el chatbot y la validación documental porque
cubren el mayor rango técnico —RAG y gobierno del conocimiento por un lado,
visión, OCR y orquestación por el otro—. Dejé el recomendador a nivel de
arquitectura por una razón de fondo: **depende de datos de empleabilidad de
egresados que ESIC probablemente aún no tiene consolidados.** Prometer un
recomendador para la semana 12 sería comprometer algo que el dato no sostiene.

**2. Anclé toda la arquitectura en Azure y Microsoft 365.**
El enunciado menciona *sistemas Microsoft* casi de pasada, y me pareció el dato
más importante del caso. La solución técnicamente más elegante que obliga a
migrar identidades y firmar contratos nuevos es, en la práctica, la peor
solución. Todo se monta sobre lo que ya existe.

**3. Construí el modelo de ROI antes que los documentos, y dejé que el
resultado me contradijera — dos veces.**
La primera corrida dio ROI negativo en el año 1 cargando todo el equipo. En vez
de maquillar la cifra, reestructuré el caso de negocio: dos vistas de costo y la
palanca de conversión, que es donde de verdad está el valor para una escuela.
Después agregué sensibilidad al volumen y el modelo me mostró algo más incómodo:
**por debajo de unas 240 consultas diarias, este proyecto no se paga solo con
eficiencia operativa.** Dejé esa tabla en el Documento 4, sección 6.2, porque
prefiero que la conversación empiece ahí y no tres meses después.
El modelo es ejecutable (`codigo/modelo_roi.py`) y todos los supuestos son
parámetros editables. Si no están de acuerdo con alguno, cámbienlo y vean qué
pasa: esa es la idea.

**4. No prometí detección de falsificaciones.**
Era la respuesta que sonaba mejor para el Escenario 2 y habría sido la primera
en fallar en producción. Ningún sistema comercial detecta falsificaciones de
forma confiable sobre un PDF escaneado, y un falso rechazo le cuesta a ESIC un
estudiante y un reclamo. Propuse en cambio un score de riesgo de cinco capas
que **enruta en vez de juzgar**, y un principio: el sistema puede aprobar
automáticamente, nunca rechazar.

**5. Dejé explícitos los supuestos que no pude verificar.**
El caso da magnitudes ("cientos de consultas", "~60% del tiempo"), no datos.
Todo el volumen de la línea base es estimación declarada, y la primera actividad
de la Fase 0 es medirla de verdad. El precio de inferencia por interacción es el
único parámetro que no pude anclar a una fuente pública: lo marco como supuesto
en vez de presentarlo como cifra oficial. Los demás —SMMLV 2026, factor
prestacional, jornada de 42 horas, TRM, precios de Document Intelligence— están
con su fuente en el Documento 4. Los ejemplos de conversación del Documento 3
llevan cifras ilustrativas, marcadas como tales: no son datos de ESIC.

**6. Usé IA para construir esta entrega, como ustedes autorizaron.**
Claude (Anthropic), para investigación de contexto —programas de ESIC, servicios
y precios vigentes de Azure, parámetros laborales colombianos 2026—, para
redacción, para acelerar el código de ejemplo, para la revisión final del código
y las cifras, para construir el demo web y para narrar el video con voz sintética. El modelo de ROI lo diseñé y lo
corrí yo; los números salieron de ejecutarlo, no de estimarlos a ojo.
Las decisiones de arquitectura, la elección de escenarios, el enfoque de
validación documental y la reestructuración del caso de negocio son mías, y las
sostengo en conversación.

Lo menciono con detalle porque para este cargo me parece parte de la respuesta:
**usar IA bien es saber qué delegarle y qué no.** Le delegué velocidad de
redacción y búsqueda. No le delegué el criterio.

---

## Preguntas que me habría gustado hacerles

El caso decía que se podían escribir. Estas son las mías, en orden de cuánto
cambiarían la propuesta:

1. **¿Cuántas consultas reciben realmente al día, por canal?** Es la pregunta
   número uno: decide si el caso de negocio se sostiene por eficiencia o si
   depende por completo de la palanca de conversión.
2. **¿Cuál es hoy la conversión de lead a matrícula y el ticket promedio?**
   Deciden si el ROI del año 2 es del 38% o de entre 243% y 477%.
3. **¿Cuál es el sistema académico y tiene API?** Es el riesgo R4 y el que más
   puede mover el cronograma de la Fase 2.
4. **¿Qué CRM usan?** Asumí uno genérico con REST y webhooks.
5. **¿Hay una decisión tomada sobre qué hacer con la capacidad liberada?**
   Es un riesgo mayor del caso de negocio, y no es técnico.

---

## Contenido de la entrega

Los **cinco documentos numerados** son los entregables que pide el caso. Esta
nota es la *"breve nota explicando qué decisiones tomaste"* que piden en el
correo; la incluyo también en PDF por comodidad de lectura.

| Archivo | Contenido |
|---|---|
| `01_Arquitectura_Solucion.pdf` | Componentes, flujo de datos, tecnologías justificadas, seguridad y escalabilidad. 7 ADR registrados. |
| `02_Plan_Implementacion.pdf` | 3 fases en 36 semanas, 4 puntos go/no-go, recursos, 9 riesgos con dueño. |
| `03_Solucion_Tecnica_Detallada.pdf` | Escenarios 1 y 2 a profundidad con código y prompts; escenario 3 a nivel de diseño. |
| `04_Evaluacion_Impacto_ROI.pdf` | Línea base, deflexión del 70,6%, costos, ROI en tres vistas, doble sensibilidad, métricas. |
| `05_Presentacion_Ejecutiva.pdf` | Una página, en términos de negocio. |
| `codigo/` | Gateway de LLM, orquestador RAG, prompts, validador documental, flujo n8n de 20 nodos, modelo de ROI, demo ejecutable (`python demo.py`), 42 pruebas y la guía `GUIA_DEMO.md`. |
| `video/` | Video narrado del ejemplo de funcionamiento (6 min), también en [GitHub](https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4). |
| Demos web | [agora-esic.vercel.app](https://agora-esic.vercel.app) · [claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7](https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7) |
| `markdown/` | Los cinco documentos en su formato fuente. |

Gracias por un caso que se deja pensar de verdad. Quedo atento a la conversación.

**Henry Taborda**
