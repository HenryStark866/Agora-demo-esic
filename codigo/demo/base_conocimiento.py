# -*- coding: utf-8 -*-
"""
base_conocimiento.py — Datos del demo.

TODO lo que hay aquí es FICTICIO y existe solo para mostrar el comportamiento
del sistema: programas, textos, precios, fechas, cupos, cifras de empleabilidad
y personas. No son datos de ESIC Medellín.
"""
from __future__ import annotations

from datetime import date, timedelta

HOY = date.today()
_VENCIDO = (HOY - timedelta(days=30)).isoformat()
_VIGENTE_HASTA = date(HOY.year + 1, 12, 31).isoformat()
_VIGENTE_DESDE = date(HOY.year, 1, 15).isoformat()

# Cada fragmento lleva los metadatos obligatorios del índice (Documento 1, 3.3).
FRAGMENTOS = [
    {
        "chunk_id": "prog-mcx-perfil-01",
        "titulo": "Máster CX — perfil y plan de estudios",
        "ruta": "Máster en Customer Experience Management > Programa > Perfil y plan",
        "contenido": (
            "El Máster en Customer Experience Management (código MCX) dura 12 meses "
            "en modalidad híbrida, con clases los viernes en la tarde y los sábados en "
            "la mañana. El plan de estudios tiene 8 módulos: estrategia de experiencia, "
            "investigación de clientes, diseño de servicios, analítica de CX, "
            "tecnología y CRM, liderazgo, gestión del cambio y proyecto final."),
        "fuente_uri": "https://esic.demo/programas/mcx",
        "tipo": "programa", "audiencia": ["todos"], "sensibilidad": "publico",
        "vigente_desde": _VIGENTE_DESDE, "vigente_hasta": _VIGENTE_HASTA,
    },
    {
        "chunk_id": "prog-mcx-req-02",
        "titulo": "Máster CX — requisitos de admisión",
        "ruta": "Máster en Customer Experience Management > Admisiones > Requisitos",
        "contenido": (
            "Para ingresar al Máster en Customer Experience Management (código MCX) se "
            "requiere título profesional universitario, mínimo 2 años de experiencia "
            "laboral y una entrevista de admisión con la coordinación académica. "
            "Se debe cargar cédula, acta de grado, certificado de notas y fotografía."),
        "fuente_uri": "https://esic.demo/programas/mcx/admisiones",
        "tipo": "programa", "audiencia": ["aspirante", "egresado", "todos"],
        "sensibilidad": "publico",
        "vigente_desde": _VIGENTE_DESDE, "vigente_hasta": _VIGENTE_HASTA,
    },
    {
        "chunk_id": "pol-egresados-03",
        "titulo": "Política de beneficios para egresados",
        "ruta": "Egresados > Beneficios > Educación continua",
        "contenido": (
            "Los egresados de ESIC tienen descuento sobre la matrícula de los másteres. "
            "El porcentaje vigente y las condiciones de pago se confirman con el área "
            "financiera en el momento de la inscripción."),
        "fuente_uri": "https://esic.demo/egresados/beneficios",
        "tipo": "politica", "audiencia": ["egresado"], "sensibilidad": "publico",
        "vigente_desde": _VIGENTE_DESDE, "vigente_hasta": _VIGENTE_HASTA,
    },
    {
        "chunk_id": "emp-mcx-04",
        "titulo": "Empleabilidad — promoción más reciente del Máster CX",
        "ruta": "Máster en Customer Experience Management > Empleabilidad",
        "contenido": (
            "De la promoción más reciente del Máster en Customer Experience Management "
            "(código MCX), el 87% estaba trabajando en roles de experiencia de cliente o marketing a "
            "los seis meses de graduarse, según la encuesta de seguimiento a egresados."),
        "fuente_uri": "https://esic.demo/programas/mcx/empleabilidad",
        "tipo": "empleabilidad", "audiencia": ["todos"], "sensibilidad": "publico",
        "vigente_desde": _VIGENTE_DESDE, "vigente_hasta": _VIGENTE_HASTA,
    },
    {
        "chunk_id": "prog-mdb-req-05",
        "titulo": "Máster Digital Business — requisitos de admisión",
        "ruta": "Máster en Digital Business > Admisiones > Requisitos",
        "contenido": (
            "Para ingresar al Máster en Digital Business (código MDB) se requiere título "
            "profesional universitario y una prueba de conocimientos digitales. No se "
            "exige experiencia laboral previa."),
        "fuente_uri": "https://esic.demo/programas/mdb/admisiones",
        "tipo": "programa", "audiencia": ["todos"], "sensibilidad": "publico",
        "vigente_desde": _VIGENTE_DESDE, "vigente_hasta": _VIGENTE_HASTA,
    },
    {
        # Contenido INTERNO: nunca debe llegar a una sesión anónima.
        "chunk_id": "int-descuentos-06",
        "titulo": "Lineamientos internos de descuentos comerciales",
        "ruta": "Comercial > Uso interno > Descuentos",
        "contenido": (
            "Uso interno. Márgenes de negociación y descuentos máximos que puede "
            "autorizar cada nivel del equipo comercial para los másteres."),
        "fuente_uri": "https://intranet.esic.demo/comercial/descuentos",
        "tipo": "politica", "audiencia": ["todos"], "sensibilidad": "interno",
        "vigente_desde": _VIGENTE_DESDE, "vigente_hasta": _VIGENTE_HASTA,
    },
    {
        # Contenido VENCIDO: el contrato de frescura lo excluye.
        "chunk_id": "prog-mcx-req-viejo",
        "titulo": "Máster CX — requisitos (versión anterior)",
        "ruta": "Máster en Customer Experience Management > Admisiones > Requisitos",
        "contenido": (
            "Requisitos del Máster en Customer Experience Management: título "
            "profesional y 1 año de experiencia laboral."),
        "fuente_uri": "https://esic.demo/programas/mcx/admisiones?v=6",
        "tipo": "programa", "audiencia": ["todos"], "sensibilidad": "publico",
        "vigente_desde": "2025-01-15", "vigente_hasta": _VENCIDO,
    },
    {
        "chunk_id": "faq-servicios-07",
        "titulo": "Preguntas frecuentes — certificados y plataforma",
        "ruta": "Estudiantes > Servicios > Preguntas frecuentes",
        "contenido": (
            "Los certificados de estudio se solicitan en el portal del estudiante y se "
            "entregan en formato digital en un máximo de 3 días hábiles. La plataforma "
            "virtual de clases está disponible 24 horas."),
        "fuente_uri": "https://esic.demo/estudiantes/faq",
        "tipo": "faq", "audiencia": ["estudiante"], "sensibilidad": "publico",
        "vigente_desde": _VIGENTE_DESDE, "vigente_hasta": _VIGENTE_HASTA,
    },
]

PROGRAMAS = {
    "MCX": "Máster en Customer Experience Management",
    "MDB": "Máster en Digital Business",
}

# Datos "en vivo" del ERP y del sistema académico (simulados, ficticios).
COHORTE_ABIERTA = f"{HOY.year + 1}-1"
DATOS_VIVOS = {
    "precios": {
        "MCX": {"programa": "MCX", "cohorte": COHORTE_ABIERTA,
                "valor_matricula_cop": 24_500_000, "cuotas_sin_interes": 12,
                "descuento_egresado_pct": 15, "nota": "valor ficticio de demostración"},
        "MDB": {"programa": "MDB", "cohorte": COHORTE_ABIERTA,
                "valor_matricula_cop": 22_800_000, "cuotas_sin_interes": 10,
                "descuento_egresado_pct": 15, "nota": "valor ficticio de demostración"},
    },
    "fechas": {
        "MCX": {"programa": "MCX", "cohorte": COHORTE_ABIERTA,
                "cierre_inscripciones": (HOY + timedelta(days=44)).isoformat(),
                "inicio_clases": date(HOY.year + 1, 1, 30).isoformat(),
                "cupos_disponibles": 8},
        "MDB": {"programa": "MDB", "cohorte": COHORTE_ABIERTA,
                "cierre_inscripciones": (HOY + timedelta(days=58)).isoformat(),
                "inicio_clases": date(HOY.year + 1, 2, 6).isoformat(),
                "cupos_disponibles": 14},
    },
}

URL_CARGA = "https://admisiones.esic.demo/cargar-documentos"

# Escenario 2: perfiles del CRM y documentos ya "leídos" por Document Intelligence.
SOLICITUDES_CRM = {
    "SOL-2026-0412": {"nombre_completo": "Laura Marcela Restrepo Ossa",
                      "numero_documento": "1.036.448.215", "programa": "MCX"},
    "SOL-2026-0419": {"nombre_completo": "María Fernanda Gómez Arango",
                      "numero_documento": "1.152.330.907", "programa": "MCX"},
    "SOL-2026-0425": {"nombre_completo": "Andrés Felipe Cardona Ruiz",
                      "numero_documento": "71.845.220", "programa": "MCX"},
    "SOL-2026-0431": {"nombre_completo": "Juan Pablo Mejía Toro",
                      "numero_documento": "1.017.225.604", "programa": "MCX"},
}
