# -*- coding: utf-8 -*-
"""
Modelo de impacto y ROI - Fabrica de IA y Automatizacion | ESIC Medellin
Caso practico - proceso de seleccion Director de Fabrica de IA

Principio de diseno del modelo: TODO supuesto es un parametro explicito y
editable. Ningun numero esta "quemado" dentro de una conclusion. El evaluador
puede cambiar cualquier supuesto y ver como se mueve el resultado.

Ejecutar:  python modelo_roi.py          (Windows)
           python3 modelo_roi.py         (Linux / macOS)
Sin dependencias externas. Python 3.9 o superior.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ==================================================================
# PARAMETROS MACRO  (fuentes citadas en 04_Evaluacion_Impacto_ROI)
# ==================================================================
TRM                    = 3_150.0    # COP/USD. TRM 15-sep-2026 = 3.109,30 + 1,3% de colchon
SMMLV_2026             = 1_750_905  # Decreto 0159 de 2026 (transitorio; mantiene el valor
                                    # del Decreto 1469 de 2025, suspendido provisionalmente)
# Carga prestacional y parafiscal sobre el salario (salarios > 2 SMMLV):
# cesantias 8,33 + intereses 1,00 + prima 8,33 + vacaciones 4,17 + pension 12,00
# + ARL 0,522 + caja 4,00 + salud 8,50 + ICBF 3,00 + SENA 2,00 = 51,85 %.
# Salud, ICBF y SENA se incluyen sin asumir la exoneracion del art. 114-1 E.T.:
# el factor es conservador.
FACTOR_PRESTACIONAL    = 1.52
HORAS_PRODUCTIVAS_ANIO = 1_848      # 42 h/sem (Ley 2101 de 2021, desde 15-jul-2026) x 44 semanas


@dataclass
class Perfil:
    nombre: str
    smmlv: float

    def costo_mes(self):  return self.smmlv * SMMLV_2026 * FACTOR_PRESTACIONAL
    def costo_anio(self): return self.costo_mes() * 12
    def costo_hora(self): return self.costo_anio() / HORAS_PRODUCTIVAS_ANIO


ANALISTA = Perfil("Analista admisiones / servicios", 3.0)
COORD    = Perfil("Coordinador de area",             5.0)

# ==================================================================
# 1. LINEA BASE - donde se va hoy el tiempo
# ==================================================================
@dataclass
class Flujo:
    nombre: str
    volumen: int        # eventos / anio
    minutos: float      # minutos de trabajo humano por evento
    deflexion: float    # fraccion de la carga que la solucion elimina o absorbe
    perfil: Perfil = field(default_factory=lambda: ANALISTA)

    def horas_base(self):   return self.volumen * self.minutos / 60
    def horas_ahorro(self): return self.horas_base() * self.deflexion
    def cop_base(self):     return self.horas_base() * self.perfil.costo_hora()
    def cop_ahorro(self):   return self.horas_ahorro() * self.perfil.costo_hora()


DIAS_HABILES         = 250
CONSULTAS_DIA        = 350    # "cientos de consultas diarias" -> extremo bajo del rango
SOLICITUDES_ADMISION = 1_800  # solicitudes con documentos / anio
NUEVOS_ESTUDIANTES   = 1_200  # estudiantes que requieren asesoria de programa
TASA_REAPERTURA      = 0.22   # consultas que se reabren o requieren seguimiento
TASA_DOC_INCOMPLETO  = 0.35   # solicitudes con al menos un ciclo de correo


def flujos_consultas(consultas_dia: float) -> list[Flujo]:
    return [
        Flujo("E1  Consultas repetitivas (estudiantes, egresados, empresas)",
              int(consultas_dia * DIAS_HABILES), 8.0, 0.72),
        Flujo("E1  Seguimiento y reapertura de consultas sin resolver",
              int(consultas_dia * DIAS_HABILES * TASA_REAPERTURA), 6.0, 0.65),
    ]


FLUJOS_OTROS = [
    Flujo("E2  Revision manual de documentos (2 h / 20 solicitudes)",
          SOLICITUDES_ADMISION, 6.0, 0.80),
    Flujo("E2  Ciclos de correo por documentos incompletos o ilegibles",
          int(SOLICITUDES_ADMISION * TASA_DOC_INCOMPLETO), 30.0, 0.75),
    Flujo("E3  Asesoria manual de eleccion de programa",
          NUEVOS_ESTUDIANTES, 45.0, 0.55),
    Flujo("ADM Reportes recurrentes (6 reportes x 12 meses)",
          72, 240.0, 0.85, COORD),
    Flujo("ADM Conciliacion manual de datos entre sistemas",
          250, 45.0, 0.80),
]

FLUJOS = flujos_consultas(CONSULTAS_DIA) + FLUJOS_OTROS

# ==================================================================
# 2. RUN RATE DE LA PLATAFORMA (USD / anio)
# ==================================================================
TASA_ATENCION_IA      = 0.85    # fraccion de consultas que pasa por la IA
COSTO_INTERACCION_USD = 0.015   # SUPUESTO: mezcla gpt-5.4-mini / gpt-5.4 + RAG + cache
# Document Intelligence: paginas por solicitud y precio por pagina (USD)
PAGINAS_DI = [  # (documento, paginas por solicitud, USD por 1.000 paginas)
    ("cedula  - prebuilt idDocument", 1, 10.0),
    ("notas   - prebuilt layout",     4, 10.0),   # 2 documentos x 2 paginas
    ("actas   - modelo custom",       2, 30.0),
]


def interacciones_ia(consultas_dia: float) -> int:
    return int(consultas_dia * DIAS_HABILES * TASA_ATENCION_IA)


def run_rate_usd(consultas_dia: float = CONSULTAS_DIA) -> dict[str, float]:
    return {
        "Azure OpenAI (Foundry) - inferencia":       interacciones_ia(consultas_dia) * COSTO_INTERACCION_USD,
        "Azure OpenAI - embeddings y reindexacion":  420.0,
        "Azure AI Search (S1, 1 SU) [estimado]":   3_000.0,
        "Azure AI Document Intelligence":          sum(SOLICITUDES_ADMISION * p / 1000 * usd
                                                       for _, p, usd in PAGINAS_DI),
        "Azure Container Apps (n8n + APIs)":       1_450.0,
        "Azure Functions, Storage, Key Vault, Monitor": 980.0,
        "Content Safety + evaluaciones continuas":   620.0,
        "WhatsApp Business API":                   2_400.0,
    }


PAGINAS_DI_ANIO = sum(SOLICITUDES_ADMISION * p for _, p, _ in PAGINAS_DI)

# ==================================================================
# 3. INVERSION DE IMPLEMENTACION - ANO 1
# ==================================================================
@dataclass
class Rol:
    nombre: str
    smmlv: float
    meses: float
    dedicacion: float
    incremental: bool

    def costo(self):
        return self.smmlv * SMMLV_2026 * FACTOR_PRESTACIONAL * self.meses * self.dedicacion


EQUIPO = [
    # incremental=False -> la contratacion ya esta decidida por ESIC (es este mismo cargo)
    #                      o es personal interno que se reasigna, no headcount nuevo.
    Rol("Director de Fabrica de IA",                         9.0, 12, 1.00, False),
    Rol("Ingeniero de IA / Backend (nuevo, mes 2)",          6.5, 11, 1.00, True),
    Rol("Ingeniero de Automatizacion (nuevo, mes 4)",        5.5,  9, 1.00, True),
    Rol("Knowledge Ops / curador de contenido (interno)",    3.5, 12, 0.50, False),
    Rol("Product Owner de negocio (interno)",                6.0, 12, 0.25, False),
]
OTROS_CAPEX_COP = 42_000_000   # pentest externo, licencias, formacion, contingencia 15%
SOSTENIMIENTO_SMMLV = 6.5 + 5.5  # ano 2+: los dos ingenieros

# Materializacion del ahorro en el ano 1 (fraccion por mes). MVP en semana 12.
CURVA_ANIO_1 = [0, 0, 0, .15, .15, .35, .55, .75, .90, 1, 1, 1]

# ==================================================================
# 4. PALANCA DE INGRESO  (el caso de negocio real de una escuela)
# ==================================================================
LEADS_ANIO          = 9_000   # leads/consultas comerciales calificables al anio
CONVERSION_ACTUAL   = 0.133   # 1.200 matriculas / 9.000 leads
LIFT_CONVERSION_PP  = 1.5     # +1,5 pp por respuesta 24/7, seguimiento automatico y nurturing
TICKETS_PROGRAMA    = [14_000_000, 22_000_000, 30_000_000]  # escenarios de ticket promedio anual
MARGEN_CONTRIBUCION = 0.45    # margen de contribucion por matricula incremental


# ==================================================================
# CALCULO (separado de la presentacion: lo usan las pruebas y el demo web)
# ==================================================================
def _ahorro_y_base(consultas_dia: float) -> tuple[float, float, float, float]:
    fl = flujos_consultas(consultas_dia) + FLUJOS_OTROS
    return (sum(f.horas_base() for f in fl), sum(f.horas_ahorro() for f in fl),
            sum(f.cop_base() for f in fl), sum(f.cop_ahorro() for f in fl))


def costo_anio_2(consultas_dia: float = CONSULTAS_DIA) -> float:
    sost = SOSTENIMIENTO_SMMLV * SMMLV_2026 * FACTOR_PRESTACIONAL * 12
    return sost + sum(run_rate_usd(consultas_dia).values()) * TRM


def roi_anio_2_volumen(consultas_dia: float) -> float:
    _, _, _, ca = _ahorro_y_base(consultas_dia)
    c2 = costo_anio_2(consultas_dia)
    return (ca - c2) / c2


def volumen_equilibrio() -> float:
    """Consultas diarias con las que el ROI del ano 2 (solo eficiencia) es cero."""
    lo, hi = 1.0, 5_000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if roi_anio_2_volumen(mid) < 0:
            lo = mid
        else:
            hi = mid
    return hi


def calcular() -> dict:
    tb, ta, cb, ca = _ahorro_y_base(CONSULTAS_DIA)
    rr = run_rate_usd()
    run_cop = sum(rr.values()) * TRM
    inc = sum(r.costo() for r in EQUIPO if r.incremental) + OTROS_CAPEX_COP
    full = sum(r.costo() for r in EQUIPO) + OTROS_CAPEX_COP
    cA1, cB1 = inc + run_cop, full + run_cop
    b1 = sum(ca / 12 * m for m in CURVA_ANIO_1)
    c2 = costo_anio_2()

    ab = ac = 0.0
    pay = None
    for i in range(60):
        ab += ca / 12 * (CURVA_ANIO_1[i] if i < 12 else 1.0)
        ac += cA1 / 12 if i < 12 else c2 / 12
        if pay is None and ab >= ac:
            pay = i + 1
    tb3, tc3 = b1 + ca * 2, cA1 + c2 * 2

    mat = LEADS_ANIO * LIFT_CONVERSION_PP / 100
    costo_consulta_ia = run_cop / interacciones_ia(CONSULTAS_DIA)
    costo_consulta_humano = ANALISTA.costo_hora() * 8 / 60
    margenes = [t * MARGEN_CONTRIBUCION for t in TICKETS_PROGRAMA]
    faltante_40 = c2 - cb * 0.40
    return {
        "horas_base": tb, "horas_ahorro": ta, "reduccion": ta / tb,
        "fte_base": tb / HORAS_PRODUCTIVAS_ANIO, "fte_ahorro": ta / HORAS_PRODUCTIVAS_ANIO,
        "cop_base": cb, "cop_ahorro": ca,
        "run_rate_usd": rr, "run_rate_cop": run_cop,
        "costo_consulta_ia": costo_consulta_ia, "costo_consulta_humano": costo_consulta_humano,
        "relacion": costo_consulta_humano / costo_consulta_ia,
        "vista_a": cA1, "vista_b": cB1, "incremental_sin_run": inc, "total_sin_run": full,
        "beneficio_a1": b1, "costo_a2": c2,
        "roi_a1_A": (b1 - cA1) / cA1, "roi_a1_B": (b1 - cB1) / cB1, "roi_a2": (ca - c2) / c2,
        "payback_mes": pay, "roi_3_anios": (tb3 - tc3) / tc3,
        "beneficio_3": tb3, "costo_3": tc3,
        "matriculas_incrementales": mat,
        "roi_conversion": [(ca + mat * m - c2) / c2 for m in margenes],
        # Cuantas matriculas incrementales pagan el run rate anual de la plataforma
        "matriculas_para_run_rate": [run_cop / m for m in margenes],
        "matriculas_para_costo_a2": [c2 / m for m in margenes],
        "deflexion_equilibrio": c2 / cb,
        "matriculas_faltante_40": faltante_40 / margenes[0],
        "volumen_equilibrio": volumen_equilibrio(),
        "paginas_di": PAGINAS_DI_ANIO,
    }


# ==================================================================
# PRESENTACION  (formato colombiano: punto de miles, coma decimal)
# ==================================================================
def num(x: float, dec: int = 0) -> str:
    s = f"{abs(x):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if x < 0 else "") + s


def money(c: float) -> str:
    return ("-$" if c < 0 else "$") + num(abs(c))


def pct(x: float, dec: int = 1) -> str:
    return num(x * 100, dec) + " %"


def line(t: str = "") -> None:
    print(("-" * 88) if not t else f"\n{'-' * 88}\n{t}\n{'-' * 88}")


def main() -> None:
    r = calcular()
    print("=" * 88)
    print(" MODELO DE IMPACTO Y ROI - FABRICA DE IA Y AUTOMATIZACION | ESIC MEDELLIN")
    print("=" * 88)
    print(f" TRM {money(TRM)} COP/USD | SMMLV 2026 {money(SMMLV_2026)} | "
          f"factor prestacional {num(FACTOR_PRESTACIONAL, 2)}")
    print(f" Costo/hora: analista {money(ANALISTA.costo_hora())} | "
          f"coordinador {money(COORD.costo_hora())}")

    line("1. LINEA BASE Y REDUCCION DE TRABAJO MANUAL")
    print(f"{'Flujo':<62}{'h base':>8}{'defl':>8}{'h ahorro':>10}")
    for f in FLUJOS:
        print(f"{f.nombre:<62}{num(f.horas_base()):>8}{pct(f.deflexion, 0):>8}"
              f"{num(f.horas_ahorro()):>10}")
    print(f"{'TOTAL':<62}{num(r['horas_base']):>8}{pct(r['reduccion']):>8}"
          f"{num(r['horas_ahorro']):>10}")
    print(f"\n  Carga manual actual ............ {num(r['horas_base']):>8} h/anio"
          f"   ({num(r['fte_base'], 1)} FTE)")
    print(f"  Carga liberada ................. {num(r['horas_ahorro']):>8} h/anio"
          f"   ({num(r['fte_ahorro'], 1)} FTE)")
    print(f"  >> REDUCCION DE TRABAJO MANUAL: {pct(r['reduccion'])}   (meta del caso: 70 %)")
    print(f"  Costo anual de la carga base ... {money(r['cop_base'])} COP")
    print(f"  Valor de la capacidad liberada . {money(r['cop_ahorro'])} COP/anio")

    line("2. RUN RATE ANUAL DE LA PLATAFORMA")
    for k, v in r["run_rate_usd"].items():
        print(f"  {k:<48}{'USD ' + num(v):>12}{money(v * TRM) + ' COP':>20}")
    tot = sum(r["run_rate_usd"].values())
    print(f"  {'TOTAL':<48}{'USD ' + num(tot):>12}{money(r['run_rate_cop']) + ' COP':>20}")
    print(f"\n  Interacciones atendidas por IA/anio: {num(interacciones_ia(CONSULTAS_DIA))}"
          f" | paginas Document Intelligence/anio: {num(r['paginas_di'])}")
    print(f"  Costo marginal por consulta atendida por IA : {money(r['costo_consulta_ia'])} COP")
    print(f"  Costo de esa misma consulta atendida a mano  : {money(r['costo_consulta_humano'])} COP")
    print(f"  >> Relacion: 1 a {r['relacion']:.0f}")

    line("3. INVERSION ANO 1")
    for ro in EQUIPO:
        tag = "INCREMENTAL" if ro.incremental else "ya aprobado/interno"
        print(f"  {ro.nombre:<50}{money(ro.costo()):>16} COP  {tag}")
    print(f"  {'Otros (pentest, licencias, formacion, contingencia)':<50}"
          f"{money(OTROS_CAPEX_COP):>16} COP  INCREMENTAL")
    print(f"\n  Vista A - costo INCREMENTAL ano 1 (equipo nuevo + otros + run rate) : "
          f"{money(r['vista_a'])} COP")
    print(f"  Vista B - costo TOTALMENTE CARGADO ano 1 (incluye direccion e internos): "
          f"{money(r['vista_b'])} COP")
    print("  Nota: el Director de Fabrica de IA es una contratacion que ESIC ya decidio")
    print("        (este proceso de seleccion). En la Vista A no se carga al proyecto.")

    line("4. ROI - EFICIENCIA OPERATIVA")
    print(f"  {'':<10}{'Beneficio':>20}{'Costo':>20}{'Neto':>20}{'ROI':>10}")
    filas = (("A ano 1", r["beneficio_a1"], r["vista_a"]),
             ("B ano 1", r["beneficio_a1"], r["vista_b"]),
             ("ano 2", r["cop_ahorro"], r["costo_a2"]),
             ("ano 3", r["cop_ahorro"], r["costo_a2"]))
    for et, b, c in filas:
        print(f"  {et:<10}{money(b):>20}{money(c):>20}{money(b - c):>20}{pct((b - c) / c):>10}")
    pay = r["payback_mes"]
    print(f"\n  Payback (Vista A, solo eficiencia): "
          f"{'mes ' + str(pay) if pay else 'no se alcanza en 60 meses'}")
    print(f"  ROI acumulado 3 anos (Vista A): {pct(r['roi_3_anios'])}   "
          f"[beneficio {money(r['beneficio_3'])} / costo {money(r['costo_3'])}]")

    line("5. PALANCA DE INGRESO - donde esta el verdadero caso de negocio")
    print(f"  Leads/anio {num(LEADS_ANIO)} | conversion actual {pct(CONVERSION_ACTUAL)} | "
          f"lift objetivo +{num(LIFT_CONVERSION_PP, 1)} pp")
    mat = r["matriculas_incrementales"]
    print(f"  Matriculas incrementales/anio: {num(mat)}\n")
    print(f"  {'Ticket anual':>14}{'Ingreso increm.':>18}{'Margen contrib.':>18}"
          f"{'ROI ano 2':>11}{'Matric. que pagan':>19}")
    print(f"  {'':>14}{'':>18}{'':>18}{'total':>11}{'el run rate':>19}")
    for t, roi, n in zip(TICKETS_PROGRAMA, r["roi_conversion"], r["matriculas_para_run_rate"]):
        print(f"  {money(t):>14}{money(mat * t):>18}{money(mat * t * MARGEN_CONTRIBUCION):>18}"
              f"{pct(roi, 0):>11}{num(n, 1):>19}")
    print(f"\n  El run rate anual de la plataforma ({money(r['run_rate_cop'])}) se paga con "
          f"{num(r['matriculas_para_run_rate'][-1], 1)} a {num(r['matriculas_para_run_rate'][0], 1)}")
    print(f"  matriculas incrementales; el costo completo del ano 2 ({money(r['costo_a2'])}), con "
          f"{num(r['matriculas_para_costo_a2'][-1])} a {num(r['matriculas_para_costo_a2'][0])}.")
    print("  El ticket promedio lo fija ESIC: el modelo entrega la palanca, no una cifra inventada.")

    line("6. SENSIBILIDAD - que pasa si la deflexion no llega al 70%")
    print(f"  {'Deflexion':>12}{'Ahorro anual':>22}{'ROI ano 2 (solo eficiencia)':>32}")
    c2 = r["costo_a2"]
    for d in (.40, .50, .60, .70, .80):
        a = r["cop_base"] * d
        print(f"  {pct(d, 0):>12}{money(a):>22}{pct((a - c2) / c2):>32}")
    print(f"\n  Punto de equilibrio en eficiencia pura: deflexion minima del "
          f"{pct(r['deflexion_equilibrio'])} para ROI positivo en ano 2.")
    print(f"  Con 40 % de deflexion, el faltante se cubre con {num(r['matriculas_faltante_40'])} "
          f"matriculas incrementales (ticket mas bajo).")

    line("7. SENSIBILIDAD AL VOLUMEN - el supuesto mas fragil de todo el modelo")
    print("  'Cientos de consultas diarias' es una magnitud, no un dato. Si el volumen")
    print("  real de ESIC Medellin es menor, el ahorro cae proporcionalmente (el costo de")
    print("  inferencia tambien baja, pero es una fraccion minima del costo).\n")
    print(f"  {'Consultas/dia':>15}{'Carga base (h)':>18}{'Ahorro anual':>20}"
          f"{'ROI ano 2':>13}{'Veredicto':>20}")
    for cd in (100, 150, 200, 250, 350, 500):
        tb_v, _, _, ca_v = _ahorro_y_base(cd)
        roi = roi_anio_2_volumen(cd)
        v = "se paga solo" if roi > .15 else ("marginal" if roi > -.05 else "NO se paga solo")
        marca = "  <-- modelado" if cd == CONSULTAS_DIA else ""
        print(f"  {cd:>15}{num(tb_v):>18}{money(ca_v):>20}{pct(roi):>13}{v:>20}{marca}")
    ve = r["volumen_equilibrio"]
    print(f"\n  Punto de equilibrio: {num(ve)} consultas diarias.")
    print(f"  Lectura honesta: por debajo de ~{num(round(ve, -1))} consultas diarias el proyecto NO se")
    print("  justifica solo por eficiencia y debe sostenerse en la palanca de conversion")
    print("  de la seccion 5. Medir esto es la primera actividad de la Fase 0.")
    print("=" * 88)


if __name__ == "__main__":
    main()
