# Documento 4 — Evaluación de Impacto y ROI
## Fábrica de IA y Automatización · ESIC Medellín

**Autor:** Henry Taborda · **Fecha:** 15 de septiembre de 2026
**Modelo ejecutable:** `codigo/modelo_roi.py` — `python modelo_roi.py` · también interactivo en la pestaña *Modelo de impacto* del demo
**Demo desplegado:** [agora-esic.vercel.app](https://agora-esic.vercel.app) · **Demo extendido** (requiere sesión en claude.ai; también en `demo_web/index.html` de la entrega): [claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7](https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7) · **Video narrado:** [ver en GitHub](https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4) (también en `video/` de la entrega) · **Repositorio:** [github.com/HenryStark866/Agora-demo-esic](https://github.com/HenryStark866/Agora-demo-esic)

---

## 0. Cómo leer este documento

Todos los números de aquí salen de un modelo que se puede ejecutar y auditar. Cada supuesto es un parámetro editable en la primera sección del archivo; ninguna cifra está escondida dentro de una conclusión. Si ESIC cree que son 500 consultas diarias y no 350, se cambia una línea y el modelo entero se recalcula.

Esa es la postura: **no vengo a defender un número, vengo a entregar el modelo.** Y dos advertencias honestas por delante:

1. **Los supuestos de volumen son estimaciones**, porque el caso da magnitudes ("cientos de consultas", "~60% del tiempo") y no datos. La primera actividad de la Fase 0 es medir la línea base real y firmarla con los líderes de área. Hasta entonces, el 70% es una hipótesis con un modelo detrás, no un hecho.
2. **El precio de inferencia es el único supuesto que no pude anclar a una fuente pública.** Lo declaro explícitamente (USD 0,015 por interacción) en vez de presentar una cifra inventada como si fuera oficial. Se valida contra la Azure Pricing Calculator en la semana 3.

### Fuentes de los parámetros macro

| Parámetro | Valor | Fuente |
|---|---|---|
| SMMLV 2026 | $1.750.905 COP | Decreto 0159 de 2026, que lo fija transitoriamente tras la suspensión provisional del Decreto 1469 de 2025 por el Consejo de Estado (mismo valor) |
| Factor prestacional | 1,52 | Cesantías (8,33%), intereses (1%), prima (8,33%), vacaciones (4,17%), pensión (12%), ARL (0,522%), caja (4%), salud (8,5%), ICBF (3%) y SENA (2%) = 51,85%. Se incluyen salud, ICBF y SENA sin asumir la exoneración del art. 114-1 E.T.: el factor es conservador |
| Jornada legal | 42 h/semana desde 15-jul-2026 | Ley 2101 de 2021 |
| Horas productivas/año | 1.848 | 42 h × 44 semanas efectivas |
| TRM de planeación | $3.150 COP/USD | TRM 15-sep-2026 = $3.109,30 + 1,3% de colchón |
| Document Intelligence | USD 1,50 / 10 / 30 por 1.000 pág. | Precios pay-as-you-go verificados 2026 |

---

## 1. Línea base: dónde se va el tiempo hoy

El caso dice que los equipos dedican ~60% del tiempo a trabajo repetitivo. Traducido a horas, con los supuestos de volumen declarados:

| Flujo | Volumen/año | Min/evento | **Horas/año** |
|---|---|---|---|
| Consultas repetitivas (4 canales) | 87.500 | 8 | **11.667** |
| Seguimiento y reapertura de casos | 19.250 | 6 | **1.925** |
| Revisión manual de documentos | 1.800 | 6 | **180** |
| Ciclos de correo por documentos incompletos | 630 | 30 | **315** |
| Asesoría manual de elección de programa | 1.200 | 45 | **900** |
| Reportes recurrentes | 72 | 240 | **288** |
| Conciliación manual entre sistemas | 250 | 45 | **188** |
| **TOTAL** | | | **15.462 h/año** |

**Equivale a 8,4 FTE.** Costo anual de esa carga: **$811.589.946 COP**.

> **Un hallazgo que cambia la prioridad del proyecto.** La revisión manual de documentos —el dolor que el caso describe con más detalle (2 h por 20 solicitudes)— son apenas **180 horas al año**. Las consultas repetitivas son **11.667**: sesenta y cinco veces más. Si hubiera que elegir un solo escenario para construir, el orden correcto es 1 → 2 → 3, y por eso el MVP de la semana 12 es el chatbot. Los ciclos de correo por documentos incompletos (315 h) cuestan casi el doble que la revisión en sí: **el problema documental no es revisar, es el ida y vuelta**, y por eso la validación ocurre en el momento de la carga.

---

## 2. Reducción de trabajo manual

| Flujo | Deflexión | Horas liberadas | Cómo |
|---|---|---|---|
| Consultas repetitivas | 72% | 8.400 | RAG multicanal + caché semántica (~40% de aciertos) |
| Seguimiento y reapertura | 65% | 1.251 | Seguimiento automatizado + *handoff* con contexto completo |
| Revisión de documentos | 80% | 144 | 5 capas de validación + auto-aprobación sobre score ≥ 85 |
| Ciclos de correo | 75% | 236 | Validación en el momento de la carga, antes de enviar |
| Asesoría de programa | 55% | 495 | Recomendador explicable; el asesor conserva la decisión |
| Reportes recurrentes | 85% | 245 | Pipeline programado → Power BI |
| Conciliación entre sistemas | 80% | 150 | Conectores idempotentes + CDC |
| **TOTAL PONDERADO** | **70,6%** | **10.921 h/año** | |

### ✅ **Meta del caso: 70% · Resultado modelado: 70,6%**

**5,9 FTE de capacidad liberada.** Valor: **$574.675.672 COP/año**.

Las tasas de deflexión no son aspiracionales: 72% en consultas está dentro del rango que alcanza un RAG bien gobernado sobre un dominio acotado con contenido curado. Las tres condiciones importan — sin curaduría de contenido, la cifra real está 20 puntos abajo, y por eso el rol de Knowledge Ops está financiado desde el día uno (riesgo R1).

---

## 3. Costo de operar la plataforma

| Componente | USD/año | COP/año |
|---|---|---|
| Azure OpenAI — inferencia (74.375 interacciones) | 1.116 | 3.514.219 |
| Azure OpenAI — embeddings y reindexación | 420 | 1.323.000 |
| Azure AI Search (S1, 1 SU) *[estimado]* | 3.000 | 9.450.000 |
| Azure AI Document Intelligence (12.600 pág.) | 198 | 623.700 |
| Azure Container Apps (n8n + APIs) | 1.450 | 4.567.500 |
| Functions, Storage, Key Vault, Monitor | 980 | 3.087.000 |
| Content Safety + evaluaciones continuas | 620 | 1.953.000 |
| WhatsApp Business API | 2.400 | 7.560.000 |
| **TOTAL** | **10.184** | **32.078.419** |

| | Costo por consulta |
|---|---|
| Atendida por IA | **$431 COP** |
| Atendida a mano | **$6.913 COP** |
| **Relación** | **1 : 16** |

> **El dato que más cuesta creer y más conviene entender:** operar toda la plataforma cuesta **$32 millones de pesos al año** — menos que un solo analista. El costo de una Fábrica de IA no son los tokens: es el equipo, la curaduría de contenido y la gobernanza. Cualquier caso de negocio que presente la nube como el gasto principal está mirando el lugar equivocado, y cualquier proveedor que venda "ahorro en infraestructura" no ha construido uno de estos.

---

## 4. Inversión año 1

| Concepto | COP |
|---|---|
| Ingeniero de IA / Backend (nuevo, 11 meses) | 190.288.355 |
| Ingeniero de Automatización (nuevo, 9 meses) | 131.738.092 |
| Pentest externo, licencias, formación, contingencia 15% | 42.000.000 |
| Run rate de plataforma | 32.078.419 |
| **VISTA A — costo incremental año 1** | **396.104.866** |
| *+ Director de Fábrica de IA (12 meses)* | *287.428.565* |
| *+ Knowledge Ops 50% y Product Owner 25% (internos)* | *103.793.649* |
| **VISTA B — costo totalmente cargado año 1** | **787.327.080** |

**Por qué dos vistas, y por qué la A es la correcta para decidir.** El Director de Fábrica de IA es una contratación que ESIC **ya decidió hacer** — es el cargo de este proceso de selección. Cargarlo al proyecto sería contar dos veces una decisión ya tomada. Knowledge Ops y el Product Owner son personal interno reasignado, no headcount nuevo. La Vista B se incluye porque un CFO la va a pedir, y porque presentar solo la cifra favorable sería hacer trampa con la contabilidad.

---

## 5. ROI

### 5.1 Solo por eficiencia operativa

| Período | Beneficio | Costo | Neto | ROI |
|---|---|---|---|---|
| Año 1 (Vista A) | 280.154.390 | 396.104.866 | −115.950.476 | **−29,3%** |
| Año 1 (Vista B) | 280.154.390 | 787.327.080 | −507.172.689 | −64,4% |
| Año 2 | 574.675.672 | 415.316.505 | +159.359.167 | **+38,4%** |
| Año 3 | 574.675.672 | 415.316.505 | +159.359.167 | **+38,4%** |

**Payback: mes 21. ROI acumulado a 3 años: +16,5%.**

El beneficio del año 1 es parcial porque el valor se materializa progresivamente: nada en los primeros 3 meses, 15% desde el MVP en la semana 12, 100% desde el mes 10.

**Y aquí está la conversación incómoda que hay que tener de frente:** *si el caso de negocio fuera solo eficiencia operativa, este proyecto sería marginal.* Un ROI de 38% al año 2 con payback en el mes 21 es aceptable, no espectacular. Presentarlo con un 300% sacado de sumar beneficios blandos sería más vendedor y menos cierto.

**El caso de negocio de una escuela de negocios no es el costo. Es la conversión.**

### 5.2 Donde está el valor real: la palanca de ingreso

El cuello de botella de ESIC no es que admisiones trabaje mucho. Es que **un aspirante que pregunta un sábado a las 9 de la noche recibe respuesta el lunes**, y para entonces ya cotizó en otras dos escuelas. Con ~9.000 leads al año y 1.200 matrículas (13,3% de conversión), cada punto de conversión son 90 matrículas.

Un lift conservador de **+1,5 puntos porcentuales** — por respuesta inmediata 24/7, seguimiento automatizado que no se cae y asesoría enriquecida — son **135 matrículas incrementales al año**:

| Ticket promedio anual | Ingreso incremental | Margen de contribución (45%) | **ROI año 2 total** |
|---|---|---|---|
| $14.000.000 | $1.890.000.000 | $850.500.000 | **243%** |
| $22.000.000 | $2.970.000.000 | $1.336.500.000 | **360%** |
| $30.000.000 | $4.050.000.000 | $1.822.500.000 | **477%** |

**El ticket promedio lo pone ESIC.** No lo invento: entrego la palanca y el modelo, y ESIC sustituye su cifra real. Con cualquiera de los tres escenarios, **entre 3 y 6 matrículas incrementales pagan el run rate anual completo de la plataforma** ($32 millones); las 135 del escenario lo cubren más de 25 veces. El costo completo del año 2, equipo incluido, se paga con entre 31 y 66 matrículas.

---

## 6. Análisis de sensibilidad

### 6.1 Qué pasa si no llegamos al 70%

| Deflexión lograda | Ahorro anual | ROI año 2 (solo eficiencia) |
|---|---|---|
| 40% | $324.635.978 | −21,8% |
| 50% | $405.794.973 | −2,3% |
| **60%** | **$486.953.967** | **+17,2%** |
| **70%** | **$568.112.962** | **+36,8%** |
| 80% | $649.271.956 | +56,3% |

**Punto de equilibrio: 51,2% de deflexión.** Por debajo de eso, el proyecto no se paga solo con eficiencia. Aun con 40% de deflexión, el faltante se cubre con unas 14 matrículas incrementales al ticket más bajo: una décima parte de la meta de conversión.

Esto es lo que quiero que quede claro: **el proyecto tiene un margen de error de casi 20 puntos porcentuales sobre la meta antes de volverse negativo.** Eso no es optimismo; es diseño de riesgo.

### 6.2 Sensibilidad al volumen — el supuesto más frágil de todo el modelo

La deflexión no es el riesgo mayor. El riesgo mayor es que *"cientos de consultas diarias"* sea una magnitud y no un dato. Modelé 350 como extremo bajo del rango, pero si ESIC Medellín —un campus relativamente joven— recibe la mitad, el ahorro cae proporcionalmente y el caso cambia:

| Consultas/día | Carga base (h/año) | Ahorro anual | ROI año 2 | Veredicto |
|---|---|---|---|---|
| 100 | 5.754 | $217.269.347 | −47,4% | No se paga solo |
| 150 | 7.696 | $288.750.612 | −30,1% | No se paga solo |
| 200 | 9.637 | $360.231.877 | −12,9% | No se paga solo |
| 250 | 11.579 | $431.713.142 | +4,2% | Marginal |
| **350** *(modelado)* | **15.462** | **$574.675.672** | **+38,4%** | **Se paga solo** |
| 500 | 21.287 | $789.119.467 | +89,3% | Se paga solo |

El costo de inferencia se recalcula con cada volumen, aunque pesa poco frente al del equipo.

**La lectura honesta: el punto de equilibrio está en 238 consultas diarias. Por debajo de unas 240, este proyecto no se justifica solo por eficiencia operativa** y tiene que sostenerse en la palanca de conversión de la sección 5.2. Por eso la primera actividad de la Fase 0 es medir el volumen real durante dos semanas, y por eso el GO/NO-GO 1 exige una línea base firmada antes de comprometer el presupuesto completo.

Prefiero entregar esta tabla que un número único. Si ESIC sustituye su cifra real en `codigo/modelo_roi.py`, el modelo entero se recalcula en un segundo.

---

## 7. Beneficios por tipo de usuario

| Usuario | Antes | Después |
|---|---|---|
| **Aspirante** | Formulario, espera 24–48 h, respuesta genérica, abandona | Respuesta en segundos, 24/7, en WhatsApp, con su caso y su contexto |
| **Estudiante** | Correo a coordinación, espera, seguimiento manual | Autoservicio inmediato para el 70% de los trámites |
| **Egresado** | Sin canal claro; la relación se enfría al graduarse | Puerta permanente: educación continua, bolsa de empleo, red. **Reactiva un activo que ESIC ya tiene y no está usando.** |
| **Empresa aliada** | Correo comercial, respuesta en días | Calificación inmediata + propuesta preliminar el mismo día |
| **Equipo de admisiones** | 60% del tiempo repitiendo lo mismo | Lo repetitivo lo absorbe el sistema; el tiempo se va a los casos que necesitan una persona |
| **Dirección** | Reportes manuales, decisiones con datos de la semana pasada | Tablero en vivo: demanda por programa, vacíos de contenido, conversión por canal |

**Un beneficio que no está en ninguna tabla:** el sistema registra **qué pregunta la gente y qué no sabe responder ESIC**. Eso es investigación de mercado continua y gratuita sobre demanda real de programas. Para una escuela de negocios que diseña oferta académica, ese dato vale por sí solo.

---

## 8. Métricas de éxito

Ninguna métrica sin línea base y sin dueño. Se revisan mensualmente en el comité.

### Negocio

| Métrica | Línea base | Meta 6 m | Meta 12 m |
|---|---|---|---|
| Reducción de trabajo manual | 0% | 45% | **70%** |
| Tiempo de primera respuesta | 24–48 h | < 1 min (IA) | < 1 min |
| Tasa de resolución sin humano | 0% | 60% | 72% |
| Conversión lead → matrícula | 13,3% | +0,8 pp | **+1,5 pp** |
| Satisfacción (CSAT) del asistente | — | ≥ 4,0/5 | ≥ 4,3/5 |
| Documentos auto-aprobados | 0% | 50% | 80% |
| Ciclo de admisión (días) | línea base F0 | −30% | −50% |

### Calidad de IA — las que evitan un desastre

| Métrica | Umbral | Acción si se incumple |
|---|---|---|
| *Groundedness* promedio | ≥ 0,85 | Bloquea despliegue |
| Acierto en conjunto dorado | ≥ 85% | Bloquea despliegue |
| Tasa de alucinación detectada | < 1% | Revisión inmediata de prompts |
| Fuga de contenido restringido | **0** | **Incidente de seguridad** |
| Acuerdo IA–humano en documentos | ≥ 95% | Suspende auto-aprobación |
| Disparidad demográfica (recomendador) | no significativa | Bloquea exposición |

### Operación

| Métrica | Meta |
|---|---|
| p95 de latencia (chatbot) | < 4 s |
| Disponibilidad | ≥ 99,5% |
| Costo por interacción | < $500 COP |
| Vacíos de contenido resueltos / detectados | ≥ 80% mensual |

**La métrica que vigilo más de cerca no es el ahorro: es la fuga de contenido restringido.** Es la única con umbral cero, porque las demás se corrigen y esa se lamenta.

---

## 9. Lo que puede salir mal con estos números

En orden de probabilidad:

1. **El volumen real es menor que el estimado.** "Cientos de consultas" podría ser 150 y no 350 — y en ese caso, como muestra la tabla 6.2, el proyecto no se paga solo con eficiencia. **Es el riesgo más grande del caso de negocio, por encima de cualquier riesgo técnico.** *Mitigación:* la medición de la Fase 0 corrige el modelo antes de comprometer el presupuesto completo, y el GO/NO-GO 1 lo bloquea si no cuadra.
2. **La capacidad liberada no se reinvierte.** Si nadie define en qué trabajan esas 5,9 FTE, el ahorro es teórico y no aparece en ningún estado financiero. **Es el otro gran riesgo del caso de negocio, y tampoco es técnico.** Requiere una decisión explícita de dirección antes de la semana 12.
3. **El lift de conversión no se materializa.** Depende de que la experiencia sea buena, no solo rápida. *Mitigación:* medición A/B desde el MVP.
4. **El contenido fuente está peor de lo esperado** y la deflexión se queda en 50%. *Mitigación:* auditoría en Fase 0 y GO/NO-GO 1 explícito.

**Sobre el punto 2 quiero ser claro incluso a costa de la propuesta:** la reducción del 70% no se traduce en ahorro contable a menos que ESIC decida qué hacer con el tiempo liberado. La recomendación es reasignar a trabajo de conversión y experiencia, no reducir personal — porque es ahí donde está el ROI de tres dígitos de la sección 5.2, y porque un equipo que teme por su puesto sabotea pasivamente el proyecto que lo amenaza (riesgo R2). **El caso de negocio y la gestión del cambio son el mismo problema.**

---

*Documento 4 de 5 · Caso Práctico Fábrica de IA y Automatización · ESIC Medellín*
