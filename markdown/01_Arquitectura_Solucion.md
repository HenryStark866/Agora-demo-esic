# Documento 1 — Arquitectura de la Solución
## Fábrica de IA y Automatización · ESIC Medellín

**Autor:** Henry Taborda · **Fecha:** 15 de septiembre de 2026
**Proyecto:** Plataforma **ÁGORA** — la puerta de entrada conversacional de ESIC y la fábrica que la sostiene
**Demo desplegado:** [agora-esic.vercel.app](https://agora-esic.vercel.app) · **Demo extendido** (requiere sesión en claude.ai; también en `demo_web/index.html` de la entrega): [claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7](https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7) · **Video narrado:** [ver en GitHub](https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4) (también en `video/` de la entrega) · **Repositorio:** [github.com/HenryStark866/Agora-demo-esic](https://github.com/HenryStark866/Agora-demo-esic)

---

## 0. La tesis en un párrafo

El problema de ESIC no es que falte un chatbot. Es que **el conocimiento institucional vive disperso en cabezas, correos y PDFs**, y cada consulta obliga a una persona a reconstruirlo desde cero. Por eso el 60% del tiempo se va en repetir. Un chatbot aislado resuelve el síntoma y crea un nuevo silo. Lo que propongo es una **fábrica**: una plataforma con componentes reutilizables —conocimiento gobernado, orquestación, observabilidad y seguridad— sobre la cual los tres escenarios del caso son los tres primeros productos, y el cuarto, el quinto y el décimo cuestan una fracción del primero. Esa es la diferencia entre automatizar tres procesos y construir una capacidad.

---

## 1. Principios de diseño

Cinco decisiones que gobiernan todo lo demás. Cuando haya que elegir, se elige por estos principios.

| # | Principio | Qué implica en la práctica |
|---|-----------|----------------------------|
| **P1** | **Apalancarse en lo que ESIC ya tiene** | El caso menciona *sistemas Microsoft*. La arquitectura se ancla en Azure y Microsoft 365: Entra ID para identidad, Graph para correo y calendario, Teams como consola del staff. Cero migraciones. El costo de adopción interna cae a casi nada. |
| **P2** | **Separar conocimiento estático de dato vivo** | RAG para lo que cambia poco (pénsums, requisitos, políticas). *Function calling* contra APIs en vivo para lo que cambia a diario (cupos, precios, fechas de cierre, estado de una solicitud). **Un precio jamás sale de un índice vectorial.** Esta sola regla elimina la mayor fuente de alucinación con consecuencias comerciales. |
| **P3** | **El humano decide lo irreversible** | La IA clasifica, extrae, redacta y recomienda. Rechazar una admisión, aprobar un documento dudoso o comprometer un descuento siempre pasa por una persona, con el contexto ya preparado. |
| **P4** | **Portabilidad deliberada** | Toda llamada a un modelo pasa por una capa de abstracción propia. Cambiar de `gpt-5.4-mini` a otro proveedor es un cambio de configuración, no un refactor. ESIC no queda rehén de un modelo ni de un precio. |
| **P5** | **Si no se mide, no existe** | Cada interacción emite trazas de costo, latencia, *groundedness* y satisfacción. La meta del 70% es un tablero, no una promesa de slide. |

---

## 2. Vista de capas

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CAPA 5 · EXPERIENCIA                                                        │
│  Widget web esic.co  ·  WhatsApp Business  ·  Microsoft Teams (staff)        │
│  Correo (Graph)      ·  Portal de admisiones  ·  Panel Power BI             │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │  HTTPS / Entra ID (OAuth 2.0 + PKCE)
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  CAPA 4 · ORQUESTACIÓN                            [Azure Container Apps]     │
│  ┌────────────────┐ ┌──────────────────┐ ┌────────────────────────────────┐ │
│  │ API Gateway    │ │ n8n (self-host)  │ │ Azure Functions                │ │
│  │ APIM + rate    │ │ flujos de negocio│ │ lógica determinista, webhooks  │ │
│  │ limit + WAF    │ │ humanos en loop  │ │ jobs de reindexación           │ │
│  └────────────────┘ └──────────────────┘ └────────────────────────────────┘ │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  CAPA 3 · INTELIGENCIA                                 [Azure AI Foundry]    │
│  Router de intención · Agentes (Consultas, Documentos, Recomendación)        │
│  Modelos: gpt-5.4-mini (80% tráfico) · gpt-5.4 (razonamiento complejo)       │
│  text-embedding-3-large · Document Intelligence · Content Safety             │
│  Prompt Shields · Evaluaciones continuas (groundedness / relevance)          │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  CAPA 2 · CONOCIMIENTO Y DATOS                                               │
│  Azure AI Search  (híbrido: BM25 + vectorial + semantic ranker)              │
│  Índices: programas · financiación · empleabilidad · políticas · FAQs        │
│  PostgreSQL (estado operativo, auditoría, consentimientos Ley 1581)          │
│  Blob Storage (documentos, cifrado CMK) · Redis (caché semántica)            │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  CAPA 1 · INTEGRACIÓN CON SISTEMAS FUENTE                                    │
│  CRM · Sistema académico (SIA) · SharePoint / OneDrive · CMS esic.co         │
│  LMS · ERP financiero · Bolsa de empleo de egresados                         │
│  Patrón: conectores idempotentes + CDC + cola de eventos (Service Bus)       │
└──────────────────────────────────────────────────────────────────────────────┘

        ╔══════════════════════════════════════════════════════════════╗
        ║  CAPA TRANSVERSAL · GOBIERNO                                 ║
        ║  Entra ID · Key Vault · Private Endpoints · App Insights     ║
        ║  Trazabilidad LLM · FinOps por interacción · Registro 1581   ║
        ╚══════════════════════════════════════════════════════════════╝
```

---

## 3. Componentes y justificación tecnológica

### 3.1 Capa de inteligencia

| Componente | Tecnología elegida | Por qué esta y no otra |
|---|---|---|
| Plataforma de modelos | **Azure AI Foundry (Azure OpenAI)** | No es solo "OpenAI con otra factura". Trae: DPA empresarial y compromiso de no entrenamiento sobre los datos del cliente; integración nativa con Entra ID y Private Link (el tráfico no sale a internet); SLA y facturación dentro del *Enterprise Agreement* que ESIC probablemente ya tiene. Usar la API pública de OpenAI obligaría a un contrato nuevo, un análisis de transferencia internacional de datos aparte y un vector de red adicional. |
| Modelo de trabajo | **`gpt-5.4-mini`** para ~80% del tráfico | El 80% de las consultas son de recuperación con síntesis corta. Un modelo de razonamiento ahí es quemar presupuesto y latencia. |
| Modelo de razonamiento | **`gpt-5.4`** | Se activa por el router cuando la consulta es multi-salto ("¿qué máster me sirve si vengo de psicología, trabajo de noche y necesito financiación?") o cuando el juicio de confianza del modelo pequeño cae bajo umbral. |
| Embeddings | **`text-embedding-3-large`** (3.072 dim) | La diferencia de costo frente a `-small` es marginal en este volumen y la ganancia en recuperación sobre español técnico y nombres de programas es real. |
| Extracción documental | **Azure AI Document Intelligence** | `prebuilt-idDocument`, `prebuilt-layout` y un modelo *custom* entrenado con actas de grado colombianas. Detalle en el Documento 3. |
| Seguridad del modelo | **Azure AI Content Safety + Prompt Shields** | Filtrado de entrada/salida y defensa contra inyección de prompt, incluida la indirecta (un PDF subido que contenga instrucciones). |

> **Estrategia anti-lock-in (P4).** Todo pasa por `llm_gateway`, una capa propia que normaliza *requests*, aplica caché, presupuesto por conversación y reintentos con espera exponencial. Detrás puede haber Azure OpenAI, Anthropic, Gemini o un modelo abierto en contenedor. La decisión de modelo es un catálogo de configuración con *routing* por tipo de tarea y techo de costo; el código entregado trae los catálogos de Azure OpenAI y de Gemini, y el demo cambia de uno a otro con un parámetro, sin tocar el orquestador.

### 3.2 Capa de orquestación — el híbrido y su razón

Esta es la decisión que más se suele equivocar, así que la justifico explícitamente.

| Herramienta | Dónde se usa | Por qué |
|---|---|---|
| **n8n** (auto-hospedado en Container Apps) | Flujos de negocio con pasos humanos: validación documental, escalamientos, *nurturing* de leads, reportes. | Auto-hospedado, los datos personales **nunca salen de la suscripción de Azure de ESIC** — condición dura bajo Ley 1581. Es visual: un coordinador de admisiones puede leer el flujo y discutirlo. Y tiene nodos de IA nativos. Versionable en Git. |
| **Power Automate** | Automatizaciones ligeras *dentro* de Microsoft 365: aprobaciones en Teams, alertas, SharePoint. | Donde ya hay conector nativo y licencia pagada, escribir código es desperdiciar. |
| **Azure Functions** | Procesamiento pesado, criptografía, validaciones deterministas, jobs de reindexación. | Las reglas de negocio críticas (¿este promedio cumple el requisito?) van en código probado con pruebas unitarias, no en un nodo de *low-code*. |

**La regla:** *low-code* para el flujo y la visibilidad; código para la lógica que, si falla, cuesta dinero o reputación. Meter validación de requisitos de admisión en un nodo visual es cómodo hasta la primera auditoría.

### 3.3 Capa de conocimiento

**Azure AI Search** con búsqueda híbrida: BM25 (léxico, imbatible para códigos de programa y nombres propios) + vectorial (semántico) + *semantic ranker* sobre el conjunto fusionado con RRF.

Cada *chunk* indexado lleva metadatos obligatorios:

```json
{
  "chunk_id": "prog-mdm-2026-req-03",
  "contenido": "...",
  "vector": [...],
  "fuente_uri": "https://esic.co/programas/master-digital-marketing",
  "tipo": "programa | financiacion | politica | faq | empleabilidad",
  "audiencia": ["aspirante", "estudiante", "egresado", "empresa"],
  "sensibilidad": "publico | interno | restringido",
  "propietario": "coordinacion.academica@esic.co",
  "vigente_desde": "2026-01-15T00:00:00Z",
  "vigente_hasta": "2026-12-31T23:59:59Z",
  "version": 7,
  "hash_origen": "sha256:..."
}
```

`vigente_hasta` no es decorativo: es un **contrato de frescura**. Un *chunk* vencido se excluye del *retrieval* automáticamente y dispara una tarea al propietario. El contenido desactualizado deja de ser un riesgo silencioso y se vuelve un ticket con dueño y fecha.

---

## 4. Flujos de datos

### 4.1 Consulta conversacional (Escenario 1)

```
Usuario → Canal → API Gateway ─┬─ AuthN (Entra ID / token anónimo firmado)
                               ├─ Rate limit + WAF
                               └─▶ Orquestador de consulta
                                     │
                                     ├─▶ [1] Content Safety + Prompt Shields
                                     ├─▶ [2] Router de intención  (gpt-5.4-nano)
                                     │        ├─ en dominio → sigue
                                     │        ├─ fuera de dominio → respuesta de política
                                     │        └─ requiere humano → deriva con contexto
                                     ├─▶ [3] Caché semántica (Redis, umbral 0,94)
                                     │        └─ acierto → responde (≈40% del tráfico)
                                     ├─▶ [4] Recuperación híbrida (AI Search)
                                     │        + filtro por audiencia, sensibilidad y vigencia
                                     ├─▶ [5] ¿Requiere dato vivo?
                                     │        └─ sí → function calling a API del SIA/CRM
                                     ├─▶ [6] Generación con grounding obligatorio + citas
                                     ├─▶ [7] Verificación de groundedness
                                     │        └─ score < 0,7 → no responde, deriva
                                     └─▶ [8] Traza: costo, latencia, fuentes, feedback
```

El paso **[7]** es lo que separa una demo de un sistema en producción. Si la respuesta generada no está respaldada por los fragmentos recuperados, **el sistema prefiere no responder**. En una institución educativa, una respuesta inventada sobre requisitos de admisión o condiciones de financiación es un problema legal, no un bug.

### 4.2 Validación documental (Escenario 2)

```
Carga de documentos → Blob (cifrado) → Service Bus → n8n
   │
   ├─ Clasificación del tipo de documento (visión)
   ├─ Extracción (Document Intelligence según tipo)
   ├─ Verificación de integridad técnica del archivo
   ├─ Validación cruzada (coherencia entre documentos y contra CRM)
   ├─ Reglas de negocio (Azure Function, determinista)
   ├─ Score de riesgo compuesto
   │     ├─ ≥ 85 y sin hallazgos críticos → auto-aprobado, escribe en SIA
   │     ├─ 50–84, o cualquier señal de riesgo → revisión humana con hallazgos precargados
   │     └─ < 50 por causas corregibles → devolución al aspirante con motivo específico
   └─ Auditoría inmutable (quién, qué, cuándo, con qué versión de modelo)
```

### 4.3 Recomendación de programa (Escenario 3 — a nivel de arquitectura)

Enfoque híbrido en tres etapas: **filtro duro** de elegibilidad (reglas, no IA) → **recuperación** por similitud entre el vector del perfil y el vector de cada programa, enriquecida con datos de empleabilidad de egresados → **re-ranking y explicación** con LLM. El modelo nunca decide solo: ordena y argumenta sobre un conjunto que ya pasó reglas auditables. Desarrollo en el Documento 2 (roadmap) y Documento 3 (sección 4).

---

## 5. Seguridad y cumplimiento

ESIC Medellín opera con **doble titulación Colombia–España**. La **Ley 1581 de 2012** aplica con certeza. Para el flujo de datos hacia la institución española, el **RGPD** muy probablemente también aplica — es un punto que hay que confirmar con jurídica en la Fase 0, no asumir. La arquitectura se diseña para cumplir ambos regímenes porque el sobrecosto de hacerlo es bajo y el de descubrirlo tarde es alto.

### 5.1 Protección de datos personales

| Exigencia | Implementación |
|---|---|
| Autorización previa, expresa e informada (art. 9, Ley 1581) | Registro de consentimiento con marca temporal, versión del aviso de privacidad y canal, en tabla append-only. Recuperable en segundos ante requerimiento de la SIC. |
| Finalidad y minimización | El chatbot anónimo opera sin PII. La identificación solo ocurre cuando el usuario pide algo que la requiere, y pidiendo el mínimo. |
| Datos sensibles (art. 5–6) | Documentos de identidad y académicos: cifrado en reposo con **llave gestionada por el cliente (CMK)** en Key Vault, acceso solo vía identidad administrada, retención con borrado automático al cierre del proceso de admisión. |
| Derechos del titular (consulta, rectificación, supresión) | Endpoint dedicado que resuelve en ≤ 10 días hábiles. La supresión propaga a índices, cachés y trazas. |
| Transferencia internacional | Despliegue en región Azure con residencia definida y DPA de Azure OpenAI. Los *prompts* no se usan para entrenar modelos. |
| Redacción de PII en telemetría | Las trazas guardan *hashes* y metadatos, no el contenido personal. Un incidente en observabilidad no es una fuga de datos. |

> Este bloque lo escribo desde experiencia directa: construí **Habeas Check**, una herramienta de autodiagnóstico de cumplimiento de Ley 1581. No estoy citando una norma que leí esta mañana.

### 5.2 Riesgos propios de IA (OWASP Top 10 para LLM)

| Riesgo | Mitigación en esta arquitectura |
|---|---|
| Inyección de prompt (directa e indirecta) | Prompt Shields; separación estricta instrucción/dato; documentos subidos tratados como contenido no confiable, nunca como instrucciones. |
| Divulgación de información sensible | Filtro por `audiencia` y `sensibilidad` en el *retrieval*, aplicado **antes** de que el modelo vea el contexto. La audiencia que propone el router se valida contra una lista cerrada antes de entrar al filtro, para que un mensaje manipulado no pueda inyectar OData. Un aspirante no puede recuperar un documento interno ni con el prompt perfecto. |
| Salida insegura / alucinación | Grounding obligatorio, umbral de *groundedness*, citas verificables, negativa explícita cuando no hay evidencia. |
| Consumo excesivo (costo) | Presupuesto por conversación verificado **antes** de cada llamada, límite de tokens, caché semántica, rate limiting por IP y por usuario. |
| Agencia excesiva | Las herramientas expuestas al modelo son de **solo lectura**. Las pocas escrituras (crear el caso en el CRM, registrar un vacío de contenido, aprobar un documento en el SIA) las ejecutan el orquestador y los flujos con reglas deterministas, nunca el modelo. El modelo no puede modificar un registro académico. |
| Envenenamiento de datos | Solo se indexa desde fuentes autorizadas con dueño identificado; cada *chunk* guarda `hash_origen`. |

### 5.3 Seguridad de infraestructura

Entra ID con MFA para todo acceso administrativo · Private Endpoints: ningún servicio de datos con IP pública · Secretos en Key Vault, rotación 90 días, cero credenciales en código · WAF y APIM al frente · Segregación de ambientes dev/stage/prod con suscripciones separadas · Pentest externo antes de producción (presupuestado) · Registro de auditoría inmutable por 5 años.

---

## 6. Escalabilidad

| Dimensión | Diseño | Techo antes de rediseñar |
|---|---|---|
| Concurrencia conversacional | Container Apps con escalado por longitud de cola KEDA; estado en Redis, contenedores sin estado | ~200 conversaciones simultáneas con 1 SU de AI Search |
| Volumen de consultas | Caché semántica absorbe ~40%; TPM de Azure OpenAI con *provisioned throughput* si la demanda se vuelve estable | 10× el volumen actual sin cambio arquitectónico |
| Corpus de conocimiento | AI Search S1 → S2 es un cambio de SKU, no de código | ~50 GB de índice |
| Documentos | Procesamiento asíncrono por cola: los picos de temporada de admisiones se absorben con latencia, no con caídas | picos de 10× sobre la media |
| Nuevos casos de uso | **Este es el punto.** Cada producto nuevo reutiliza autenticación, RAG, orquestación, observabilidad y gobierno. | El escenario 4 cuesta ~20% de lo que costó el primero |

**Lo que deliberadamente NO se hace ahora:** *fine-tuning* (RAG bien hecho resuelve el 95% a una fracción del costo y sin deuda de reentrenamiento); base de datos vectorial propia (AI Search cubre el volumen de ESIC por años); multi-nube (complejidad sin beneficio a esta escala); agentes autónomos con capacidad de escritura amplia (riesgo desproporcionado frente al valor). Cada una de estas puertas queda abierta, ninguna se abre sin una métrica que lo justifique.

---

## 7. Decisiones de arquitectura registradas

| ID | Decisión | Alternativa descartada | Razón |
|---|---|---|---|
| ADR-01 | Azure AI Foundry como plataforma de modelos | API pública de OpenAI / Bedrock | Alineación con el stack Microsoft existente (P1), DPA y residencia, identidad unificada |
| ADR-02 | RAG híbrido, no *fine-tuning* | Modelo afinado con datos de ESIC | El conocimiento cambia cada semestre; reentrenar es insostenible. RAG actualiza en minutos |
| ADR-03 | n8n auto-hospedado + Functions + Power Automate | Solo Power Automate / solo código | Ver 3.2. Visibilidad para negocio, rigor donde importa, datos dentro de Azure |
| ADR-04 | Datos transaccionales vía *function calling*, nunca indexados | Indexar todo, incluido precios y cupos | Un precio desactualizado en una respuesta es un compromiso comercial en falso |
| ADR-05 | Capa propia de abstracción de LLM | Llamar el SDK del proveedor directamente | Portabilidad, control de costo y caché centralizados (P4) |
| ADR-06 | Umbral de *groundedness* con negativa explícita | Responder siempre | Prefiero "no sé, te conecto con admisiones" a una respuesta inventada sobre requisitos |
| ADR-07 | PostgreSQL para estado operativo | Cosmos DB | El modelo es relacional y el volumen no justifica el costo ni la complejidad de Cosmos |

---

## 8. Cómo esta arquitectura ataca el 70%

| Fuente del 60% de tiempo perdido | Componente que lo ataca | Reducción modelada |
|---|---|---|
| Consultas repetitivas en cuatro canales | Chatbot RAG multicanal con caché y derivación con contexto | 72% |
| Reapertura y seguimiento de casos | Seguimiento automatizado en n8n + contexto completo al humano | 65% |
| Revisión manual documento por documento | Document Intelligence + validación cruzada + score de riesgo | 80% |
| Ciclos de correo por documentos incompletos | Validación en el momento de la carga, antes de enviar | 75% |
| Asesoría manual de elección de programa | Recomendador híbrido explicable | 55% |
| Reportes recurrentes armados a mano | Pipeline programado → Power BI | 85% |
| Conciliación manual entre sistemas | Conectores idempotentes + CDC | 80% |

**Total ponderado: 70,6%** sobre 15.462 horas/año de carga base. El cálculo completo, con todos sus supuestos y su análisis de sensibilidad, está en el Documento 4 y en `codigo/modelo_roi.py`, ejecutable. Los pasos del flujo 4.1 y del 4.2 se pueden ver funcionando en el demo interactivo y con `python demo.py`.

---

*Documento 1 de 5 · Caso Práctico Fábrica de IA y Automatización · ESIC Medellín*
