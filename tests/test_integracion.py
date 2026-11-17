"""Prueba de integración: endpoint + lógica de negocio + base de datos funcionando juntos."""
from unittest import mock

from rest_framework.test import APITestCase

from polizas.models import Poliza

ASEGURADO = "8f1c2a3b-0000-4000-8000-000000000002"


@mock.patch("polizas.views.publicar")
@mock.patch("polizas.views.get_json", return_value={"kyc_status": "verificado"})
class PolizaIntegracionTests(APITestCase):
    def test_emitir_consultar_renovar_y_cancelar_en_base_de_datos(self, get_json, publicar):
        datos = {"id_asegurado": ASEGURADO, "product_type": "hogar", "coverage": {"plan": "premium", "suma_asegurada": 250000000},
                 "effective_date": "2026-01-01", "expiry_date": "2026-12-31"}
        resp = self.client.post("/api/v1/polizas", datos, format="json")
        self.assertEqual(resp.status_code, 201)
        id_poliza = resp.data["id_poliza"]
        self.assertTrue(Poliza.objects.filter(pk=id_poliza, status="activa").exists())
        self.assertEqual(self.client.get(f"/api/v1/polizas/{id_poliza}").data["product_type"], "hogar")
        self.assertEqual(self.client.put(f"/api/v1/polizas/{id_poliza}/renovar", {"meses": 12}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/polizas/{id_poliza}/cancelar").status_code, 200)
        self.assertEqual(Poliza.objects.get(pk=id_poliza).status, "cancelada")
        eventos = [c[0][0] for c in publicar.call_args_list]
        self.assertEqual(eventos, ["policy.issued", "policy.renewed", "policy.cancelled"])
