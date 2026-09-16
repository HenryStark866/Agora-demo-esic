# Documento 3 — Solución Técnica Detallada
## Fábrica de IA y Automatización · ESIC Medellín

**Autor:** Henry Taborda · **Fecha:** 15 de septiembre de 2026
**Alcance:** Escenarios 1 y 2 desarrollados a profundidad · Escenario 3 a nivel de diseño
**Código acompañante:** carpeta `codigo/` — ver `codigo/README.md` · ejecutable con `python demo.py` · 42 pruebas
**Demo desplegado:** [agora-esic.vercel.app](https://agora-esic.vercel.app) · **Demo extendido** (requiere sesión en claude.ai; también en `demo_web/index.html` de la entrega): [claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7](https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7) · **Video narrado:** [ver en GitHub](https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4) (también en `video/` de la entrega) · **Repositorio:** [github.com/HenryStark866/Agora-demo-esic](https://github.com/HenryStark866/Agora-demo-esic)

---

# ESCENARIO 1 · Chatbot inteligente para consultas

## 1.1 Las tres preguntas del caso

### ¿Qué LLM usarías y por qué?

**La pregunta correcta no es cuál, sino cuántos.** Usar un solo modelo para todo el tráfico es el error de costo más caro y más común en estos proyectos: el 80% de las consultas de ESIC son recuperación con síntesis corta ("¿cuáles son los requisitos del máster en Digital Business?"), y resolverlas con un modelo de razonamiento es pagar veinte veces de más por una respuesta más lenta.

El diseño enruta por tipo de tarea (`codigo/comun/llm_gateway.py`):

| Tarea | Modelo | Por qué |
|---|---|---|
| Clasificación de intención y verificación | `gpt-5.4-nano` | Salida JSON y esfuerzo de razonamiento bajo. Es una función, no una conversación. |
| Respuesta con RAG — **~80% del tráfico** | `gpt-5.4-mini` | Con el contexto correcto recuperado, la síntesis es la parte fácil. Latencia baja, costo bajo. |
| Razonamiento multi-salto | `gpt-5.4` | Se activa solo cuando el router marca `complejidad: compleja`: comparar programas, evaluar el perfil del usuario contra varias condiciones. |
| Embeddings | `text-embedding-3-large` | 3.072 dimensiones. La diferencia de costo frente a `-small` es marginal a este volumen y la ganancia en recuperación sobre nombres de programas en español es medible. |

**Y la decisión más importante: sobre Azure AI Foundry, no sobre la API pública de OpenAI.** No es una preferencia de marca, son cuatro razones concretas:

1. El caso dice que ESIC integra **sistemas Microsoft**. Azure OpenAI hereda Entra ID, Private Link y el Enterprise Agreement existente. Cero contratos nuevos, cero identidades nuevas.
2. **DPA empresarial con compromiso de no entrenamiento** sobre los datos del cliente. Con datos de aspirantes bajo Ley 1581 y RGPD, esto no es negociable.
3. **Private Link**: el tráfico de inferencia no sale a internet público.
4. **Residencia de datos configurable**, necesaria para el flujo de doble titulación Colombia–España.

Usar la API pública de OpenAI obligaría a un contrato aparte, un análisis de transferencia internacional independiente y un vector de red adicional. Es más trabajo jurídico por menos control.

**Y sin quedar atados.** Todo pasa por `LLMGateway` (ADR-05): el catálogo de modelos es un diccionario por proveedor. El código entregado trae el de Azure OpenAI, el de Gemini y uno para cualquier API compatible con OpenAI; el demo cambia de proveedor con `--proveedor`, sin tocar el orquestador. Migrar es cambiar ese catálogo y correr el conjunto dorado: con 150 preguntas evaluadas automáticamente, comparar dos proveedores toma horas, no un trimestre.

**Una nota sobre la coherencia.** Los modelos GPT-5.x de razonamiento no exponen `temperature`; el gateway no la envía y controla el esfuerzo de razonamiento. La consistencia de las respuestas no depende de ese parámetro sino del grounding obligatorio y del verificador del paso 7.

---

### ¿Cómo garantizarías información actualizada y precisa?

Cuatro mecanismos que se refuerzan. Ninguno basta solo.

**1. Separar conocimiento estático de dato vivo (ADR-04) — el mecanismo que más importa.**

El error clásico es indexarlo todo, incluidos precios y fechas. Seis semanas después el bot afirma con total seguridad un precio del semestre pasado y ESIC tiene un compromiso comercial en falso.

En este diseño, **un precio, un cupo, una fecha de cierre o el estado de una solicitud nunca salen del índice vectorial.** Salen de `function calling` contra la API en vivo del SIA o del CRM. El prompt de sistema lo dice de forma explícita y el catálogo de herramientas lo refuerza:

```python
{"type": "function", "function": {
    "name": "consultar_precio_vigente",
    "description": ("Precio, formas de pago y descuentos vigentes de un programa. "
                    "ÚSALA SIEMPRE que el usuario pregunte por costos. "
                    "Jamás respondas un precio sin llamar esta función."),
    ...}}
```

**2. Contrato de frescura en el índice.** Cada fragmento lleva `vigente_desde`, `vigente_hasta` y `propietario`. El filtro de recuperación excluye lo vencido automáticamente:

```python
# La audiencia la propone el router (un LLM): se valida contra una lista cerrada
# antes de interpolarla, para que un mensaje manipulado no pueda inyectar OData.
audiencia = ctx.audiencia if ctx.audiencia in AUDIENCIAS_VALIDAS else "desconocido"
ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")   # Edm.DateTimeOffset
filtro = (f"(audiencia/any(a: a eq '{audiencia}') or audiencia/any(a: a eq 'todos')) and "
          f"search.in(sensibilidad, '{','.join(niveles)}', ',') and "
          f"vigente_desde le {ahora} and vigente_hasta ge {ahora}")
```

Un documento vencido deja de responder y dispara una tarea a su dueño. El contenido desactualizado pasa de ser un riesgo silencioso a un ticket con nombre y fecha.

**3. Grounding obligatorio con verificación posterior.** La respuesta generada se vuelve a evaluar contra los fragmentos que la originaron. Si no está respaldada, **no se envía**:

```python
g = self._verificar(texto, fragmentos, datos_vivos, ctx)
if g["veredicto"] == "rechazado" or g["score"] < UMBRAL_GROUNDEDNESS:
    return self._derivar(mensaje, ctx, historial,
                         f"respuesta sin respaldo suficiente ({g['score']:.2f})")
```

El verificador tiene **tolerancia cero** en cuatro categorías —precios, fechas, requisitos y garantías—: una afirmación sin respaldo en cualquiera de ellas rechaza la respuesta sin importar el puntaje global.

**4. Evaluación continua contra el conjunto dorado.** 150 preguntas reales con respuesta validada por el negocio, construidas en la Fase 0. Cada cambio de prompt, de modelo o de estrategia de *chunking* dispara la corrida en CI. Una caída de *groundedness* bloquea el despliegue. **Sin esto no hay forma objetiva de saber si el sistema mejoró o empeoró**, y todo se vuelve opinión.

---

### ¿Cómo manejarías consultas fuera de dominio?

No todas las "consultas fuera de dominio" son iguales, y tratarlas igual es un error de producto. Hay cuatro casos:

| Caso | Ejemplo | Respuesta del sistema |
|---|---|---|
| **Ajeno al dominio** | "¿Cómo va el partido?" | Respuesta cortés + dos ejemplos de lo que sí resuelve. Sin regaño, sin disculpa larga. |
| **Adyacente al dominio** | "¿Qué máster hay en la Universidad X?" | No compite ni descalifica: reconoce, no responde por terceros y reencuadra hacia la oferta de ESIC. |
| **En dominio pero sin evidencia** | Pregunta legítima que el índice no cubre | **Aquí está el valor real.** Se registra como *vacío de conocimiento* con su audiencia y canal, y se deriva a un humano. Cada falla se convierte en una tarea concreta para Knowledge Ops. |
| **Adversario** | Inyección de prompt, extracción del prompt de sistema | Prompt Shields + filtro de sensibilidad en el *retrieval*. El contenido restringido **nunca entra al contexto**, así que ningún prompt puede extraerlo. |

El código:

```python
if not ruta["en_dominio"]:
    return Resultado(texto=("Solo puedo ayudarte con temas de ESIC Medellín. "
                            "Por ejemplo: requisitos de admisión de un máster, "
                            "opciones de financiación o servicios para egresados. "
                            "¿Te sirve alguno de esos?"), fuentes=[])

if not fragmentos and not ruta["requiere_dato_vivo"]:
    self._registrar_vacio(mensaje, ctx)     # alimenta el backlog de contenido
    return self._derivar(mensaje, ctx, historial,
                         "sin evidencia en la base de conocimiento")
```

Un chatbot que nunca reconoce lo que no sabe pierde la confianza del usuario en la tercera interacción. **La negativa honesta es una característica del producto, no una limitación.**

---

## 1.2 Estrategia de *chunking*

El *chunking* determina el techo de calidad del RAG más que el modelo. Segmentación **por estructura semántica, no por número de caracteres**:

| Tipo de contenido | Unidad de *chunk* | Tamaño | Solapamiento |
|---|---|---|---|
| Ficha de programa | Sección completa (perfil, plan, requisitos, salidas) | 400–800 tok | 0 (secciones autocontenidas) |
| Políticas y reglamentos | Artículo o numeral | 200–600 tok | 50 tok |
| FAQs | Par pregunta–respuesta completo | 100–300 tok | 0 |
| Datos de empleabilidad | Registro estructurado → texto | 150 tok | 0 |

Dos decisiones que resuelven problemas reales:

**Enriquecimiento con contexto del padre.** Cada *chunk* se indexa precedido de su ruta jerárquica: `Máster en Digital Business > Admisiones > Requisitos`. Sin esto, un fragmento que dice "se requiere un año de experiencia" es inútil porque no se sabe de qué programa habla.

**Índice de preguntas hipotéticas.** Para cada *chunk* se generan 3 preguntas que ese fragmento respondería, y se indexan sus vectores apuntando al mismo *chunk*. El usuario pregunta como usuario, el documento está escrito como documento institucional; esta capa cierra esa brecha y sube la recuperación de forma notable, con un costo de indexación que se paga una sola vez.

---

## 1.3 Integración con los sistemas existentes

| Sistema | Patrón | Dirección | Notas |
|---|---|---|---|
| CMS esic.co | Webhook al publicar → reindexación incremental | Lectura | Contenido actualizado en el índice en menos de 5 minutos |
| SharePoint / OneDrive | Indexer nativo de AI Search + Graph API | Lectura | Respeta permisos de origen |
| CRM | REST + webhooks | Lectura y escritura acotada | Crear caso, registrar interacción. **Nunca modificar oportunidades.** |
| Sistema académico (SIA) | API REST; si no existe, capa anticorrupción sobre vistas de BD | Lectura + 3 escrituras acotadas | Riesgo R4: Fase 0 lo valida antes de comprometer fechas |
| Microsoft Teams | Bot Framework + tarjetas adaptables | Bidireccional | Consola del asesor humano |
| WhatsApp | Business Cloud API | Bidireccional | Plantillas aprobadas para mensajes proactivos |
| Correo | Microsoft Graph | Bidireccional | Clasificación y borrador de respuesta; **el envío lo confirma un humano** |

---

## 1.4 Ejemplo de funcionamiento

**Consulta de un egresado** (la del caso: programa + financiación + empleabilidad), ejecutada con `python demo.py --escenario 1`. Es la salida real del orquestador de producción sobre servicios simulados; programas, precios, fechas y cifras son **ficticios** y las fechas se calculan a partir del día de ejecución.

```
 USUARIO  › Me gradué de ESIC en 2022 de Dirección de Marketing Global. Estoy pensando en el
            máster en Customer Experience. ¿Hay descuento para egresados, qué tan bien se
            están colocando los que lo terminan y hasta cuándo hay inscripciones?

 [1] Seguridad de entrada .......... limpio
 [2] Router (gpt-5.4-nano) ......... financiacion · egresado · confianza 0.94
                                      dato vivo: sí · compleja · en dominio: sí
 [3] Caché semántica ............... omitida (hay dato vivo)
 [4] Recuperación híbrida .......... filtro: audiencia=egresado · público · vigente hoy
      F1 · Máster CX — requisitos de admisión                         score 0.95
      F2 · Política de beneficios para egresados                      score 0.92
      F3 · Empleabilidad — promoción más reciente del Máster CX       score 0.89
      F4 · Máster CX — perfil y plan de estudios                      score 0.85
      excluido por vencido: Máster CX — requisitos (versión anterior)
 [5] Datos en vivo ................. consultar_precio_vigente(MCX, 2027-1)
                                      → matrícula $24.500.000 · 12 cuotas · dto. egresado 15 %
                                      consultar_fechas_admision(MCX)
                                      → cierre 2026-10-30 · cupos 8
 [6] Generación (gpt-5.4) .......... 4 frases con citas
 [7] Verificación de groundedness .. score 1.00 · APROBADO
 [8] Seguridad de salida ........... limpia
```

**Respuesta entregada:**

> Como egresado de ESIC tienes un descuento del 15% sobre la matrícula del Máster en Customer Experience Management [DV]. De la promoción más reciente del Máster en Customer Experience Management, el 87% estaba trabajando en roles de experiencia de cliente o marketing a los seis meses de graduarse, según la encuesta de seguimiento a egresados [F3]. Las inscripciones cierran el 2026-10-30 y quedan 8 cupos [DV]. ¿Quieres que te agende una sesión con un asesor de másteres esta semana?

Nota lo que **no** hace: el descuento y la fecha de cierre no salen del índice (se consultan en vivo, citados como `[DV]`), no promete empleo, no redondea la cifra de empleabilidad, descarta la versión vencida de los requisitos, cita todo lo que afirma y cierra con **una** acción concreta.

**Cuando la respuesta no tiene respaldo.** El caso 8 del demo fuerza una alucinación: al preguntar por la empleabilidad de un programa que no tiene ese dato en el índice, el generador inventa *"el 100% de los egresados consigue empleo antes de graduarse"*. El verificador la marca como afirmación sin respaldo, el veredicto es **RECHAZADO** y el usuario recibe:

> Prefiero no darte un dato que no tengo confirmado. Le paso tu consulta a un asesor de admisiones con todo el contexto; te responde hoy mismo en horario hábil. ¿Me confirmas tu correo?

En paralelo se crea el caso en el CRM con el resumen para el asesor. **La falla produce trabajo útil en vez de un error silencioso.** El demo recorre nueve casos en total: consulta con dato vivo, requisitos, caché semántica, pregunta fuera de dominio, pregunta sin evidencia (vacío registrado para Knowledge Ops), contenido interno excluido por el filtro, inyección de prompt bloqueada, alucinación rechazada y petición explícita de hablar con una persona.

---

# ESCENARIO 2 · Automatización de validación documental

## 2.1 Las tres preguntas del caso

### ¿Qué tecnologías usarías para OCR y extracción?

**Azure AI Document Intelligence**, con el modelo elegido según el tipo de documento. Elegir bien no es un detalle técnico: es la diferencia entre USD 1,50 y USD 30 por cada 1.000 páginas.

| Documento | Modelo | Precio / 1.000 pág. | Por qué |
|---|---|---|---|
| Cédula de ciudadanía | `prebuilt-idDocument` | USD 10 | Entrenado en documentos de identidad. Extrae número, nombres y fechas con campos tipados y confianza por campo. |
| Transcript de notas | `prebuilt-layout` | USD 10 | Preserva estructura de tabla, que es todo el contenido de un transcript. |
| Certificado laboral | `prebuilt-layout` | USD 10 | Formato libre, se necesita la estructura. |
| **Acta de grado / diploma** | **Modelo custom** | USD 30 | Aquí sí se justifica: cada universidad colombiana tiene su formato. Entrenado con ~50 muestras etiquetadas por institución. |
| Documento simple, solo texto | `prebuilt-read` | USD 1,50 | Se usa donde no se necesita estructura. |

*Precios pay-as-you-go verificados en 2026; hay niveles de compromiso que bajan Read hasta USD 0,45.*

**Por qué Document Intelligence y no Tesseract ni AWS Textract:**

- **Frente a Tesseract**: Tesseract hace OCR, no extracción estructurada. Habría que construir y mantener toda la capa de comprensión de layout. Sobre escaneos colombianos de calidad variable —fotos con el celular, inclinadas, con sombra— la diferencia de precisión es grande. Y el costo real de Tesseract no es la licencia, es el ingeniero manteniéndolo.
- **Frente a AWS Textract**: es comparable técnicamente, pero implicaría una segunda nube, otro perímetro de seguridad, otro DPA y otra factura. Contradice el principio P1.
- **Frente a un LLM multimodal solo**: excelente para clasificar y para casos raros, pero más caro y menos determinista para extracción masiva de campos tipados. **Se usa como complemento, no como reemplazo**: DI extrae los campos, el LLM clasifica el tipo de documento y redacta el mensaje al aspirante.

### ¿Cómo validarías la información (por ejemplo, autenticidad)?

**Empiezo por lo que no voy a decir.** Ningún sistema comercial detecta falsificaciones de manera confiable sobre un PDF escaneado. Prometer detección de fraude en esta prueba sería la respuesta que suena mejor y la que fallaría primero en producción, con consecuencias legales para ESIC al rechazar a un aspirante legítimo.

Lo que sí se puede construir es un **score de riesgo compuesto por cinco capas de evidencia independientes**, que enruta en lugar de juzgar:

| Capa | Qué evalúa | Ejemplos de señal |
|---|---|---|
| **1 · Extracción** | ¿Se pudo leer? | Confianza de OCR < 0,75 → *escaneo deficiente*, no fraude. Mensaje distinto, resultado distinto. |
| **2 · Integridad técnica** | El contenedor del archivo | Productor Photoshop/Canva (−20); texto superpuesto sobre la imagen (−30); fechas internas incoherentes (−15); **firma digital válida (+25)** |
| **3 · Reglas de negocio** | Coherencia interna, en código determinista | Fecha de grado futura (−80); promedio fuera de escala (−60); cédula con formato inválido (−60); edad imposible (−70) |
| **4 · Fuente autoritativa** | **La única evidencia real de autenticidad** | Verificación del código SNIES contra el registro del MEN; código QR o de verificación de la institución emisora; convenio directo con IES de alto volumen |
| **5 · Coherencia cruzada** | El mismo dato en cuatro lugares | Nombre que no coincide entre cédula, acta y formulario (−55); documento distinto al del formulario (−80); **archivo idéntico ya cargado en otra solicitud (−70)** |

La capa 5 es la más valiosa y la que un humano hace peor: comparar el mismo campo entre cuatro documentos y el CRM, cientos de veces, sin equivocarse. La capa 4 es la única que prueba algo; las demás acumulan evidencia.

```python
@staticmethod
def _score(docs, cruzados) -> int:
    """100 = limpio. Cada hallazgo resta su peso; la firma digital suma."""
    penal  = sum(h.peso for d in docs for h in d.hallazgos)
    penal += sum(h.peso for h in cruzados)
    return max(0, min(100, 100 - penal))
```

**Y el enrutamiento, que es donde está el ahorro:**

```
score ≥ 85 y sin hallazgos críticos   → auto-aprobado, escribe en el sistema académico
50 ≤ s < 85, o cualquier señal de riesgo → revisión humana, con los hallazgos ya señalados
score < 50 por causas corregibles      → devolución al aspirante con motivo específico
```

Dos reglas duras acotan el score (`ValidadorDocumental._decidir`): **con un hallazgo crítico nunca se auto-aprueba** —una firma digital válida no compensa un número de documento que no coincide— y **solo se devuelve automáticamente lo que el aspirante puede corregir** (documento faltante, escaneo ilegible). Un archivo duplicado o un PDF con capas superpuestas nunca se devuelven solos: los decide una persona. El correo al aspirante se redacta únicamente con los hallazgos corregibles, para que jamás describa una señal de riesgo. La comparación de nombres es insensible al orden de las palabras, porque la cédula colombiana pone los apellidos primero.

El revisor deja de abrir 20 PDFs completos para revisar 3 casos con los puntos dudosos ya marcados. **Ese es el 80% de reducción**: no porque la IA reemplace el criterio, sino porque el criterio se aplica solo donde hace falta.

**Cómo se despliega sin riesgo (Fase 2, semanas 18–22).** Modo sombra primero: el sistema decide y el humano también, se comparan durante dos semanas. **No se automatiza nada hasta que el acuerdo supere el 95%** (GO/NO-GO 3). Luego la auto-aprobación se abre por tipo de documento, empezando por cédulas y terminando en transcripts. Y toda corrección humana se registra como dato de entrenamiento del modelo custom (nodo 13 del flujo n8n).

**Un principio que no se negocia:** el sistema puede **aprobar** de forma automática, nunca **rechazar**. Un falso rechazo le cuesta a ESIC un estudiante y un reclamo; un falso aprobado lo detecta la siguiente etapa del proceso. La asimetría del error define el diseño.

### ¿Dónde orquestarías todo esto (n8n, Lambda, otro)?

**Híbrido, y la línea divisoria es explícita** (ADR-03):

| Capa | Herramienta | Responsabilidad |
|---|---|---|
| **Flujo** | **n8n** auto-hospedado en Azure Container Apps | Secuencia, esperas, reintentos, bifurcaciones, pasos humanos, notificaciones |
| **Lógica** | **Azure Functions** (Python) | Validación, reglas de negocio, score, criptografía. Probado con pruebas unitarias. |
| **M365** | **Power Automate** | Aprobaciones en Teams, alertas, SharePoint — donde ya hay conector y licencia |

**Por qué n8n y no solo Power Automate:**

1. **Soberanía del dato.** Auto-hospedado, los documentos de identidad **nunca salen de la suscripción de Azure de ESIC**. Bajo Ley 1581, con datos sensibles, esto es una condición dura.
2. **Legibilidad para el negocio.** El coordinador de admisiones abre el flujo y entiende el proceso. Puede discutirlo y proponer cambios. Ese diálogo es la mitad del trabajo de adopción.
3. **Versionable en Git**, desplegable por CI/CD, con ambientes separados. Un flujo de Power Automate editado a mano en producción es deuda técnica invisible.
4. **Costo**: no escala por usuario ni por ejecución premium.

**Y por qué la lógica NO va en n8n:** las reglas de admisión son auditables y tienen consecuencias. "¿Este promedio cumple el requisito?" vive en código con pruebas unitarias y control de versiones, no en un nodo visual que alguien puede modificar sin dejar rastro. *Low-code* para el flujo y la visibilidad; código para lo que, si falla, cuesta dinero o reputación.

**Por qué no AWS Lambda:** funcionaría perfectamente. Pero introduce una segunda nube en una organización Microsoft: otro perímetro de seguridad, otro DPA, otro modelo de identidad, otro contrato. Azure Functions da lo mismo dentro del perímetro que ya existe.

El flujo completo, con sus 20 nodos, está en `codigo/escenario2_documentos/n8n_flujo_validacion.json`, importable en n8n (las credenciales se asignan al importar). Incluye la validación de la firma HMAC sobre el cuerpo crudo, antivirus, modo sombra, la tarjeta de Teams con botones que reanudan la ejecución, la bifurcación según la decisión del revisor, el escalamiento a 48 horas y el recordatorio al aspirante a las 72 horas.

---

## 2.2 Ejemplo de funcionamiento

Salida real de `python demo.py --escenario 2` (documentos ficticios; la extracción de Document Intelligence está simulada).

**Solicitud de máster con cuatro documentos:**

```
 SOL-2026-0412 · maestría · cedula.pdf · acta_grado.pdf · notas.pdf · foto.jpg

 cedula.pdf ........................ cedula · confianza OCR 0.96
 acta_grado.pdf .................... acta_grado · confianza OCR 0.93
 notas.pdf ......................... transcript_notas · confianza OCR 0.91
 foto.jpg .......................... fotografia · confianza OCR 1.00

   info        FIRMA_DIGITAL_VALIDA       +25  El documento tiene firma digital válida.
   cruce de nombres cédula ↔ formulario: similitud 1.00 (umbral 0,85)

 SCORE ............................. 100/100  →  AUTO_APROBADO
 Trazabilidad ...................... validador v3.2.0 · 6 págs · DI USD 0.108
 Llave de idempotencia ............. SOL-2026-0412-b0728eab5b08
 Siguiente paso (n8n) .............. escribe en el SIA y notifica al aspirante
```

La cédula dice `RESTREPO OSSA LAURA MARCELA` y el formulario `Laura Marcela Restrepo Ossa`: similitud 1,00, porque la comparación no depende del orden. Tiempo humano consumido: 0 minutos (línea base: 6).

**Y un caso que va a revisión:**

```
   advertencia META_EDITOR_IMAGEN         -20  El archivo fue generado con un editor de…
   advertencia SIN_PROMEDIO               -25  No se identifica el promedio acumulado.
   cruce de nombres cédula ↔ formulario: similitud 0.96 (umbral 0,85)

 SCORE ............................. 55/100  →  REVISION_HUMANA
 Siguiente paso (n8n) .............. tarjeta en Teams con los hallazgos señalados
```

El revisor recibe en Teams una tarjeta con dos puntos señalados. **Resuelve en segundos** lo que antes exigía abrir y leer cuatro PDFs. La diferencia GOMEZ/GOMES no disparó alerta porque la similitud de 0,96 está sobre el umbral: es una variación de transcripción, no una inconsistencia. Un umbral mal calibrado aquí genera cientos de falsos positivos y mata la adopción en dos semanas.

Los otros dos casos del demo: una cédula borrosa con el certificado de notas faltante (score 0 → **DEVOLVER**, con un correo que explica qué corregir y usa el enlace de carga real) y un acta idéntica a otra ya cargada en otra solicitud (score 30, pero es señal de riesgo → **REVISION_HUMANA**, no se devuelve de forma automática).

---

# ESCENARIO 3 · Sistema de recomendación (diseño)

No lo desarrollo a nivel de código porque el caso pide dos escenarios a profundidad y porque **este depende de datos que ESIC debe consolidar primero** (empleabilidad de egresados). Prometer un recomendador para la semana 12 sería comprometer algo que el dato no sostiene.

**Enfoque: híbrido en tres etapas.** Ni IA generativa sola (alucina programas y no razona sobre datos de empleabilidad) ni ML puro (sin volumen histórico suficiente y sin capacidad de explicar).

```
Perfil del estudiante (encuesta + CRM + carrera previa)
   │
   ├─ ETAPA 1 · FILTRO DURO — reglas, sin IA
   │    elegibilidad: título previo, experiencia mínima, idioma, modalidad,
   │    disponibilidad horaria, presupuesto declarado
   │    → deja 4-8 programas candidatos, todos viables. AUDITABLE.
   │
   ├─ ETAPA 2 · RECUPERACIÓN — similitud vectorial
   │    vector(perfil) vs vector(programa enriquecido con datos de egresados
   │    de perfil similar y su empleabilidad real)
   │    → ordena por afinidad
   │
   └─ ETAPA 3 · RE-RANKING Y EXPLICACIÓN — LLM
        reordena con criterio y ARGUMENTA cada recomendación contra el perfil
        → 3 opciones, cada una con su porqué y con su contra
```

**¿Cómo asegurar recomendaciones justas y sin sesgo?** Cuatro medidas concretas:

1. **Exclusión estructural de atributos protegidos.** Género, edad, estrato, origen y colegio de procedencia no entran al vector de perfil ni al prompt. No es suficiente —hay correlatos— pero es el piso.
2. **Auditoría de disparidad antes de exponer.** Se mide la distribución de recomendaciones por grupo demográfico sobre perfiles sintéticos equivalentes que difieren solo en el atributo protegido. Si el mismo perfil con distinto género recibe recomendaciones distintas, no sale a producción (GO/NO-GO 4).
3. **Explicación obligatoria.** Toda recomendación viene con su razón trazable. Una recomendación que no se puede explicar no se muestra. La explicabilidad es el mecanismo de control de sesgo más práctico que existe: hace visible el criterio.
4. **El humano conserva la decisión.** El sistema prepara la conversación del asesor, no la reemplaza. Reduce el tiempo de asesoría en 55%, no en 100%, y esa diferencia es deliberada.

**Un sesgo que casi nadie menciona y que aquí importa:** el sesgo comercial. Es tentador que el recomendador empuje los programas con cupos libres. No lo hace, y el criterio de ordenamiento es auditable precisamente para poder demostrarlo. Un recomendador en el que el estudiante no confía no vale nada, y la confianza se pierde una sola vez.

**¿Qué datos se necesitan y cómo se obtienen?**

| Dato | Fuente | Estado probable | Acción |
|---|---|---|---|
| Perfil del aspirante | Encuesta de 8 preguntas en el portal | No existe | Diseñar en Fase 3 |
| Carrera previa y experiencia | CRM + formulario | Existe, incompleto | Enriquecer |
| Catálogo de programas | CMS + académica | Existe | Vectorizar |
| **Empleabilidad de egresados** | Bolsa de empleo + encuesta + LinkedIn | **Disperso — el cuello de botella** | Consolidar en semanas 25–28 |
| Trayectorias históricas | Sistema académico | Existe | Extraer patrones |

---

# Contenido de la carpeta `codigo/`

| Archivo | Qué contiene |
|---|---|
| `demo.py` | **Ejecutable.** Recorre los Escenarios 1 y 2 de punta a punta con el orquestador y el validador reales |
| `modelo_roi.py` | Modelo de impacto **ejecutable**: todas las cifras del Documento 4 |
| `comun/llm_gateway.py` | Capa de abstracción de modelos: catálogos por proveedor, enrutamiento por tarea, presupuesto, reintentos, caché, telemetría (ADR-05) |
| `comun/cliente_http.py` | Cliente compatible con OpenAI sin dependencias (Gemini y otros proveedores); la clave se lee de variables de entorno |
| `escenario1_chatbot/prompts.py` | Los 4 prompts de sistema: router, generador con RAG, verificador de *groundedness*, preparación de *handoff* |
| `escenario1_chatbot/orquestador.py` | Pipeline completo de 8 pasos del chatbot y derivación con contexto |
| `escenario2_documentos/validador.py` | Las 5 capas de validación, score de riesgo y reglas de decisión |
| `escenario2_documentos/n8n_flujo_validacion.json` | Flujo de 20 nodos, importable en n8n |
| `demo/` | Datos ficticios y servicios simulados (índice, ERP, CRM, Document Intelligence, LLM determinista) |
| `pruebas/` | 42 pruebas unitarias: `python -m unittest discover -s pruebas -t .` |

El orquestador y el validador son los mismos módulos que irían a producción: en el demo se les inyectan servicios simulados; en producción, los clientes reales de Azure, el CRM y el SIA.

## Cómo probarlo

1. **En el navegador, sin instalar nada:** abrir [agora-esic.vercel.app](https://agora-esic.vercel.app) (demo desplegado con backend en Supabase Edge Functions) o el demo extendido (requiere sesión en claude.ai) [https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7](https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7), que agrega la validación documental editable, el modelo de ROI interactivo, el video y el motor *Claude (real)*. Sin cuenta de Claude, la misma página se abre desde `demo_web/index.html` en la entrega.
2. **En consola:** con Python 3.9 o superior, desde la carpeta `codigo/`, ejecutar `python demo.py`. No requiere dependencias ni claves.
3. **Con un modelo real desde consola:** definir `GEMINI_API_KEY` y ejecutar `python demo.py --proveedor gemini`.

La guía paso a paso está en `codigo/GUIA_DEMO.md`.

---

*Documento 3 de 5 · Caso Práctico Fábrica de IA y Automatización · ESIC Medellín*
