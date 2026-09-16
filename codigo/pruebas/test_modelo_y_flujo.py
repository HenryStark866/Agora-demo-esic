# -*- coding: utf-8 -*-
"""Las cifras que citan los documentos salen del modelo; el flujo n8n es coherente."""
import json
import os
import unittest

import modelo_roi as m

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestModeloROI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = m.calcular()

    def test_cifras_citadas_en_los_documentos(self):
        r = self.r
        self.assertEqual(round(r["horas_base"]), 15462)
        self.assertEqual(round(r["horas_ahorro"]), 10921)
        self.assertEqual(round(r["reduccion"] * 100, 1), 70.6)
        self.assertEqual(round(r["fte_ahorro"], 1), 5.9)
        self.assertEqual(round(r["cop_ahorro"]), 574_675_672)
        self.assertEqual(round(r["run_rate_cop"]), 32_078_419)
        self.assertEqual(round(r["vista_a"]), 396_104_866)
        self.assertEqual(round(r["vista_b"]), 787_327_080)
        self.assertEqual(round(r["costo_consulta_ia"]), 431)
        self.assertEqual(round(r["costo_consulta_humano"]), 6913)
        self.assertEqual(round(r["relacion"]), 16)
        self.assertEqual(r["payback_mes"], 21)
        self.assertEqual(round(r["roi_a2"] * 100, 1), 38.4)
        self.assertEqual(round(r["roi_3_anios"] * 100, 1), 16.5)
        self.assertEqual([round(x * 100) for x in r["roi_conversion"]], [243, 360, 477])
        self.assertEqual(round(r["deflexion_equilibrio"] * 100, 1), 51.2)
        self.assertEqual(r["paginas_di"], 12_600)
        self.assertEqual(round(r["volumen_equilibrio"]), 238)

    def test_una_sola_matricula_no_paga_el_run_rate(self):
        # Corrección de la versión anterior de los documentos.
        self.assertTrue(all(n > 1 for n in self.r["matriculas_para_run_rate"]))

    def test_formato_negativo(self):
        self.assertEqual(m.money(-1500), "-$1.500")


class TestFlujoN8N(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "escenario2_documentos", "n8n_flujo_validacion.json"),
                  encoding="utf-8") as f:
            cls.wf = json.load(f)

    def test_nodos_tienen_campos_obligatorios(self):
        ids = set()
        for n in self.wf["nodes"]:
            for k in ("id", "name", "type", "typeVersion", "position", "parameters"):
                self.assertIn(k, n, f"{n.get('name')} sin {k}")
            self.assertNotIn(n["id"], ids)
            ids.add(n["id"])

    def test_conexiones_apuntan_a_nodos_existentes(self):
        nombres = {n["name"] for n in self.wf["nodes"]}
        for origen, salidas in self.wf["connections"].items():
            self.assertIn(origen, nombres)
            for rama in salidas["main"]:
                for destino in rama:
                    self.assertIn(destino["node"], nombres)

    def test_no_hay_nodos_huerfanos(self):
        destinos = {d["node"] for s in self.wf["connections"].values()
                    for rama in s["main"] for d in rama}
        disparadores = {n["name"] for n in self.wf["nodes"] if "webhook" in n["type"].lower()
                        and n["type"].endswith("webhook")}
        for n in self.wf["nodes"]:
            if n["name"] not in disparadores:
                self.assertIn(n["name"], destinos, f"{n['name']} no recibe entrada")

    def test_las_esperas_continuan(self):
        for n in self.wf["nodes"]:
            if n["type"] == "n8n-nodes-base.wait":
                self.assertIn(n["name"], self.wf["connections"],
                              f"{n['name']} es un callejón sin salida")

    def test_correos_tienen_destinatario(self):
        for n in self.wf["nodes"]:
            if n["type"] == "n8n-nodes-base.microsoftOutlook":
                self.assertIn("toRecipients", n["parameters"], n["name"])

    def test_numero_de_nodos_documentado(self):
        self.assertEqual(len(self.wf["nodes"]), 20)


if __name__ == "__main__":
    unittest.main()
