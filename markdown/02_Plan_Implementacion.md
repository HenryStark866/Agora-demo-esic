# Documento 2 — Plan de Implementación
## Fábrica de IA y Automatización · ESIC Medellín

**Autor:** Henry Taborda · **Fecha:** 15 de septiembre de 2026
**Horizonte:** 36 semanas hasta capacidad instalada · MVP en producción en la semana 12
**Demo desplegado:** [agora-esic.vercel.app](https://agora-esic.vercel.app) · **Demo extendido** (requiere sesión en claude.ai; también en `demo_web/index.html` de la entrega): [claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7](https://claude.ai/artifact/4hRWPEMq5yAzw7Ch6q9ts7) · **Video narrado:** [ver en GitHub](https://github.com/HenryStark866/Agora-demo-esic/blob/main/video/Demo_Fabrica_IA_Henry_Taborda.mp4) (también en `video/` de la entrega) · **Repositorio:** [github.com/HenryStark866/Agora-demo-esic](https://github.com/HenryStark866/Agora-demo-esic)

---

## 0. El criterio que ordena el plan

La forma más común de fracasar en esto es construir seis meses en silencio y estrenar algo que nadie pidió. La segunda más común es sacar un piloto bonito que nunca llega a producción porque no se pensó la seguridad ni el gobierno del contenido.

Este plan evita ambas con una regla: **valor medible en producción cada 4 semanas, y ningún avance de fase sin criterio de salida cumplido.** Hay cuatro *go / no-go* explícitos. Si uno no se cumple, se para y se corrige. Prefiero reportar un retraso de tres semanas que un éxito que no existe.

---

## 1. Fases

### FASE 0 · Fundación — semanas 1 a 4

*Nadie ve nada todavía, y es la fase que decide el proyecto.*

| Semana | Entregable |
|---|---|
| 1 | Mapa real de la demanda: muestreo de 2 semanas de consultas en los 4 canales, clasificadas por tipo, canal, tiempo de resolución y reapertura. **Sin esto, el 70% es una opinión.** |
| 1–2 | Inventario de fuentes: qué sistema es autoritativo para qué dato. Quién es dueño de cada contenido. Dónde está desactualizado. |
| 2 | Línea base medida y firmada por los líderes de admisiones, servicios estudiantiles y administración. Es el número contra el cual se evaluará todo. |
| 2–3 | Landing zone en Azure: suscripciones, redes, Entra ID, Key Vault, private endpoints, CI/CD, ambientes dev/stage/prod. |
| 3 | Evaluación de impacto en protección de datos (Ley 1581 + RGPD), avisos de privacidad actualizados, política de uso de IA. |
| 3–4 | Conjunto dorado de evaluación: 150 preguntas reales con respuesta correcta validada por el negocio. **Este es el activo más valioso de la fase.** Sin él no hay forma objetiva de saber si el bot mejora o empeora. |
| 4 | Arquitectura validada con TI de ESIC. Backlog priorizado por valor/esfuerzo. |

> **GO/NO-GO 1 (fin de semana 4):** línea base cuantificada y firmada · landing zone operativa · conjunto dorado listo · aval de protección de datos. *Si el contenido fuente está tan desactualizado que no se puede indexar con confianza, se para y se hace saneamiento de contenido primero.* Es un riesgo real y prefiero enfrentarlo en la semana 4 y no en la 11.

---

### FASE 1 · MVP en producción — semanas 5 a 12

**Alcance deliberadamente estrecho:** Escenario 1, limitado a **programas de máster y su financiación**, en dos canales (web y WhatsApp). Un dominio, hecho bien, en producción y con usuarios reales.

| Semana | Hito |
|---|---|
| 5–6 | Pipeline de ingesta y primer índice. Chunking, metadatos, contrato de frescura. Capa `llm_gateway`. |
| 6–8 | Orquestador de consulta: router de intención, recuperación híbrida, generación con citas, verificación de *groundedness*, derivación a humano con contexto. |
| 8–9 | Consola de agente en Microsoft Teams: el asesor recibe el caso con el historial y las fuentes ya consultadas. |
| 9–10 | Endurecimiento: Content Safety, Prompt Shields, rate limiting, presupuesto por conversación, redacción de PII en trazas. |
| 10 | Evaluación contra el conjunto dorado + prueba con 10 usuarios internos. |
| 11 | **Piloto cerrado**: 100 aspirantes reales, con opción visible de hablar con una persona. |
| 12 | **Producción** en esic.co y WhatsApp para el dominio de másteres. Tablero de métricas en vivo. |

> **GO/NO-GO 2 (semana 10):** ≥ 85% de acierto en el conjunto dorado · *groundedness* ≥ 0,85 · cero fugas de contenido restringido en pruebas adversariales · p95 de latencia < 4 s.

---

### FASE 2 · Ampliación y automatización documental — semanas 13 a 24

| Semanas | Frente | Entregable |
|---|---|---|
| 13–16 | Escenario 1 | Ampliación a pregrado, programas ejecutivos, Level Up y formación empresarial. Canal Teams para staff. Bucle de mejora con los vacíos detectados en producción. |
| 13–18 | Escenario 2 | Clasificación y extracción documental, validación cruzada, motor de reglas, score de riesgo, cola de revisión humana. |
| 18–20 | Escenario 2 | Integración de escritura con el sistema académico. Modo sombra: el sistema decide, el humano también, se comparan. **No se automatiza nada hasta que el acuerdo supere el 95%.** |
| 20–22 | Escenario 2 | Auto-aprobación progresiva: primero solo cédulas, luego certificados, al final transcripts. |
| 22–24 | Transversal | Pipeline de reportes recurrentes → Power BI. Pentest externo. Plan de respuesta a incidentes. |

> **GO/NO-GO 3 (semana 20):** acuerdo IA-humano ≥ 95% en modo sombra · cero falsos aprobados en documentos marcados como problemáticos · aprobación de Registro y Control.

---

### FASE 3 · Recomendador e industrialización — semanas 25 a 36

| Semanas | Entregable |
|---|---|
| 25–28 | Consolidación de datos de empleabilidad de egresados. Vectorización de perfiles de programa. |
| 28–32 | Recomendador híbrido: filtro de elegibilidad → similitud → re-ranking explicado. Auditoría de sesgo antes de exponerlo. |
| 32–34 | Prueba A/B contra asesoría tradicional, midiendo satisfacción y conversión. |
| 34–36 | **Industrialización de la fábrica:** catálogo de componentes reutilizables, plantillas de proyecto, proceso formal de admisión de solicitudes, transferencia de conocimiento, documentación viva. |

> **GO/NO-GO 4 (semana 32):** sin disparidad estadísticamente significativa entre grupos demográficos · satisfacción ≥ la de asesoría humana · el 100% de las recomendaciones con explicación trazable.

---

## 2. Línea de tiempo

```
SEMANA    1     4       8      12      16      20      24      28      32      36
          ├─────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
FASE 0    ████████
FASE 1            ████████████████
FASE 2                            ████████████████████████
FASE 3                                                    ████████████████████████
                 ▲           ▲                   ▲                       ▲
              G/NG 1      G/NG 2              G/NG 3                  G/NG 4
              sem. 4      sem. 10             sem. 20                 sem. 32

PRODUCCIÓN                       ▓ MVP               ▓ Documentos            ▓ Recomendador
                                 sem. 12             sem. 22                 sem. 34
```

---

## 3. Recursos

### 3.1 Equipo

| Rol | Dedicación | Origen | Responsabilidad |
|---|---|---|---|
| **Director de Fábrica de IA** | 100%, 12 meses | Este cargo | Arquitectura, priorización, gobierno, interlocución con negocio y TI, entrega hands-on en Fase 0–1 |
| **Ingeniero de IA / Backend** | 100%, desde mes 2 | Nueva contratación | RAG, orquestación, evaluaciones, integraciones |
| **Ingeniero de Automatización** | 100%, desde mes 4 | Nueva contratación | n8n, conectores, pipeline documental, reportes |
| **Knowledge Ops** | 50%, 12 meses | Interno (comunicaciones/academia) | Dueño del contenido: curaduría, vigencia, corrección de vacíos |
| **Product Owner de negocio** | 25%, 12 meses | Interno (admisiones) | Prioriza, valida, es la voz del usuario |
| Líder de TI / Seguridad | Puntual | Interno | Aprobaciones de infraestructura y seguridad |
| Asesoría jurídica | Puntual | Interno/externo | Validación de protección de datos |

**El equipo arranca con dos personas, no con cinco.** En la Fase 0 el director trabaja con Knowledge Ops y el PO. Los ingenieros entran cuando hay algo definido que construir. Contratar un equipo completo antes de saber qué se va a construir es la forma más cara de descubrirlo.

### 3.2 Inversión

| Concepto | Año 1 (COP) |
|---|---|
| Equipo incremental (2 ingenieros nuevos) | 322.026.447 |
| Pentest externo, licencias, formación, contingencia 15% | 42.000.000 |
| Run rate de plataforma Azure (año completo) | 32.078.419 |
| **Total incremental año 1** | **396.104.866** |
| *Totalmente cargado (incluye dirección y personal interno)* | *787.327.080* |

Desglose, supuestos y ROI en el Documento 4.

### 3.3 Modelo operativo de la fábrica

Terminada la Fase 3, la fábrica opera con un proceso, no con buena voluntad:

- **Admisión de solicitudes:** formulario único. Toda idea entra por ahí, con problema, volumen, dueño y valor esperado.
- **Priorización quincenal:** puntaje por valor de negocio, volumen, viabilidad técnica y riesgo. Comité con negocio y TI.
- **Definición de terminado:** en producción · con métricas en tablero · con evaluación automatizada · con dueño de contenido asignado · documentado · con plan de reversión.
- **Revisión trimestral:** qué se construyó, qué ahorró, qué se debe apagar. **Apagar cosas que no rinden es parte del trabajo.**

---

## 4. Riesgos

Ordenados por exposición (probabilidad × impacto).

| # | Riesgo | P | I | Mitigación | Dueño |
|---|---|---|---|---|---|
| **R1** | **Calidad del contenido fuente.** El RAG hereda la desactualización de los PDFs. Es el riesgo más subestimado de todos. | Alta | Alto | Auditoría de contenido en Fase 0; contrato de frescura con `vigente_hasta`; rol de Knowledge Ops financiado desde el día uno; el bot no responde sin evidencia vigente. | Knowledge Ops |
| **R2** | **Resistencia del equipo humano.** Si admisiones percibe reemplazo, el proyecto muere por sabotaje pasivo. | Media | Alto | Narrativa explícita de reasignación, no de recorte, firmada por dirección. Los asesores participan desde la Fase 0 definiendo el conjunto dorado. Se mide "horas liberadas hacia trabajo de mayor valor", no "personas reducidas". | Director + RRHH |
| **R3** | **Alucinación con consecuencia comercial o legal.** | Media | Muy alto | Umbral de *groundedness* con negativa explícita; datos vivos por API, nunca por índice; citas visibles; evaluación continua con alerta por regresión; disclaimer en temas de financiación. | Director |
| **R4** | **Integración con el sistema académico más lenta de lo previsto.** Sistemas heredados sin API es el escenario más probable. | Alta | Medio | Fase 0 valida la viabilidad antes de comprometer fechas. Plan B por exportaciones programadas y RPA acotado. El Escenario 1 no depende de escritura, así que el MVP no se bloquea. | Ing. Automatización |
| **R5** | **Incidente de datos personales.** | Baja | Muy alto | Private endpoints, CMK, minimización, redacción de PII en trazas, pentest previo a producción, plan de respuesta con notificación a la SIC dentro de plazo. | Director + TI |
| **R6** | **Costo de inferencia fuera de control.** | Media | Medio | Presupuesto por conversación, caché semántica, enrutamiento a modelo pequeño por defecto, alerta al 70% del presupuesto mensual, tablero de costo por interacción. | Director |
| **R7** | **Dependencia de un proveedor de modelos.** | Media | Medio | Capa `llm_gateway`; evaluación trimestral de alternativas; el conjunto dorado permite comparar proveedores objetivamente en horas. | Ing. IA |
| **R8** | **Sesgo en el recomendador.** | Media | Alto | Exclusión de atributos protegidos; auditoría de disparidad antes de exponer; explicación obligatoria; el asesor humano conserva la decisión. | Director |
| **R9** | **Dependencia de una sola persona.** | Media | Alto | Documentación como parte de la definición de terminado; pair programming; ningún componente con un solo conocedor a partir de la semana 20. | Director |

---

## 5. Lo que necesito de ESIC

Para que este plan se cumpla, no basta con el equipo:

1. **Un patrocinador ejecutivo** que desbloquee accesos y arbitre prioridades. Sin esto, la Fase 0 se estira tres meses esperando permisos.
2. **Acceso real a los sistemas fuente** en las primeras dos semanas, incluido el sistema académico.
3. **Dueños de contenido nombrados** por área. No se puede tercerizar la veracidad del contenido a la fábrica.
4. **Autorización para medir**: la línea base exige instrumentar canales actuales durante dos semanas.
5. **Mandato explícito sobre el destino de la capacidad liberada.** Si nadie define en qué se reinvierten esas 5,9 FTE, el ahorro se evapora y el proyecto no muestra resultado.

---

*Documento 2 de 5 · Caso Práctico Fábrica de IA y Automatización · ESIC Medellín*
