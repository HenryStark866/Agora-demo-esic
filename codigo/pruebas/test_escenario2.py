# -*- coding: utf-8 -*-
"""Pruebas del validador documental del Escenario 2 (sin red)."""
import unittest
from datetime import date, timedelta

from comun.llm_gateway import LLMGateway
from demo import simulados as sim
from escenario2_documentos.validador import (Decision, Hallazgo, TipoDoc,
                                             ValidadorDocumental, normalizar_nombre,
                                             similitud_nombres)

CRM = {"S1": {"nombre_completo": "Laura Marcela Restrepo Ossa",
              "numero_documento": "1036448215"}}


class CRMFijo:
    def obtener_solicitud(self, sid):
        return CRM.get(sid, {})


def validador(storage=None, llm=None):
    return ValidadorDocumental(sim.DocIntelSimulado(),
                               llm or LLMGateway(sim.ClienteLLMSimulado()),
                               CRMFijo(), sim.SIASimulado(),
                               storage or sim.StorageSimulado())


def paquete(nombre_ced="RESTREPO OSSA LAURA MARCELA", doc="1036448215",
            nacimiento="1996-04-18", conf_ced=0.96, sufijo="", **extra):
    a = sim.archivo
    return [
        a(f"cedula{sufijo}.pdf", "cedula", {"nombre_completo": nombre_ced,
                                            "numero_documento": doc,
                                            "fecha_nacimiento": nacimiento}, conf_ced),
        a(f"acta{sufijo}.pdf", "acta_grado", {"nombre_graduado": "Laura Marcela Restrepo Ossa",
                                              "institucion": "Universidad Demo",
                                              "fecha_grado": extra.get("grado", "2019-12-06"),
                                              "codigo_snies": "104312"}, 0.93, 2,
          extra.get("meta_acta")),
        a(f"notas{sufijo}.pdf", "transcript_notas",
          {"promedio_acumulado": extra.get("promedio", "4,1"), "escala": 5,
           "creditos_aprobados": 162}, 0.91, 2),
        a(f"foto{sufijo}.jpg", "fotografia", {}),
    ]


class TestValidador(unittest.TestCase):
    def test_solicitud_limpia_se_auto_aprueba(self):
        r = validador().validar("S1", paquete(sufijo="a"), "maestria")
        self.assertEqual(r.decision, Decision.AUTO_APROBADO)
        self.assertEqual(r.score, 100)
        self.assertEqual(r.mensaje_aspirante, "")

    def test_orden_de_apellidos_no_genera_falso_positivo(self):
        a = normalizar_nombre("RESTREPO OSSA LAURA MARCELA")
        b = normalizar_nombre("Laura Marcela Restrepo Ossa")
        self.assertEqual(similitud_nombres(a, b), 1.0)

    def test_variacion_de_transcripcion_tolerada(self):
        s = similitud_nombres(normalizar_nombre("GOMES ARANGO MARIA FERNANDA"),
                              normalizar_nombre("María Fernanda Gómez Arango"))
        self.assertGreaterEqual(s, 0.85)

    def test_hallazgo_critico_impide_auto_aprobacion_aunque_haya_firma(self):
        firma = {"firma_digital_valida": True, "firmante": "U"}
        r = validador().validar("S1", paquete(doc="999999999", sufijo="b",
                                              meta_acta=firma), "maestria")
        self.assertTrue(any(h.codigo == "DOCUMENTO_NO_COINCIDE" for h in r.hallazgos))
        self.assertNotEqual(r.decision, Decision.AUTO_APROBADO)

    def test_senal_de_riesgo_va_a_humano_no_se_devuelve(self):
        st = sim.StorageSimulado()
        docs = paquete(sufijo="c")
        st.registrar(docs[1]["bytes"], "OTRA")
        r = validador(st).validar("S1", docs, "maestria")
        self.assertLess(r.score, 50)
        self.assertEqual(r.decision, Decision.REVISION_HUMANA)

    def test_faltante_y_borroso_se_devuelve_con_correo_sin_acusar(self):
        docs = paquete(conf_ced=0.6, sufijo="d")[:2] + paquete(sufijo="d")[3:]
        r = validador().validar("S1", docs, "maestria", url_carga="https://x.demo/cargar")
        self.assertEqual(r.decision, Decision.DEVOLVER)
        self.assertIn("https://x.demo/cargar", r.mensaje_aspirante)
        for palabra in ("fraude", "falsific", "sospech"):
            self.assertNotIn(palabra, r.mensaje_aspirante.lower())

    def test_senales_de_riesgo_no_se_comunican_al_aspirante(self):
        v = validador()
        docs = [d for d in paquete(sufijo="e", meta_acta={"producer": "Canva"})
                if not d["nombre"].startswith("notas")]
        r = v.validar("S1", docs, "maestria", url_carga="https://x.demo")
        texto = v._redactar(r, "https://x.demo")
        self.assertNotIn("editor de imágenes", texto)

    def test_hallazgos_de_documento_se_incluyen_en_el_resultado(self):
        r = validador().validar("S1", paquete(conf_ced=0.6, sufijo="f"), "maestria")
        self.assertIn("OCR_BAJA_CONFIANZA", [h.codigo for h in r.hallazgos])

    def test_fecha_ilegible_no_rompe_el_proceso(self):
        r = validador().validar("S1", paquete(nacimiento="18 de abril", sufijo="g"),
                                "maestria")
        self.assertIn("FECHA_ILEGIBLE", [h.codigo for h in r.hallazgos])

    def test_fecha_formato_colombiano_se_acepta(self):
        r = validador().validar("S1", paquete(nacimiento="18/04/1996", sufijo="h"),
                                "maestria")
        self.assertEqual(r.decision, Decision.AUTO_APROBADO)

    def test_fecha_de_grado_futura_es_critica(self):
        futura = (date.today() + timedelta(days=60)).isoformat()
        r = validador().validar("S1", paquete(grado=futura, sufijo="i"), "maestria")
        self.assertIn("FECHA_GRADO_FUTURA", [h.codigo for h in r.hallazgos])

    def test_promedio_con_coma_decimal(self):
        r = validador().validar("S1", paquete(promedio="4,5", sufijo="j"), "maestria")
        self.assertNotIn("PROMEDIO_FUERA_ESCALA", [h.codigo for h in r.hallazgos])

    def test_documento_no_reconocido_se_senala(self):
        docs = paquete(sufijo="k") + [sim.archivo("otro.pdf", "desconocido", {})]
        r = validador().validar("S1", docs, "maestria")
        self.assertIn("DOC_NO_RECONOCIDO", [h.codigo for h in r.hallazgos])

    def test_falla_del_llm_usa_plantilla(self):
        class Roto:
            def completar(self, **kw):
                raise RuntimeError("sin servicio")
        docs = paquete(sufijo="l")[:1]
        r = validador(llm=Roto()).validar("S1", docs, "maestria", url_carga="https://u")
        self.assertEqual(r.decision, Decision.DEVOLVER)
        self.assertIn("https://u", r.mensaje_aspirante)

    def test_tipo_de_programa_desconocido(self):
        with self.assertRaises(ValueError):
            validador().validar("S1", [], "doctorado")

    def test_decision_es_pura(self):
        crit = Hallazgo("NOMBRE_NO_COINCIDE", "critico", "x", peso=55)
        self.assertEqual(ValidadorDocumental._decidir(95, [crit]), Decision.REVISION_HUMANA)
        self.assertEqual(ValidadorDocumental._decidir(90, []), Decision.AUTO_APROBADO)


if __name__ == "__main__":
    unittest.main()
