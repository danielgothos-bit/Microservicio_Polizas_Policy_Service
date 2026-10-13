import uuid
from unittest import mock

from rest_framework.test import APITestCase

from comun.clientes import ServicioNoDisponible

ASEGURADO = str(uuid.uuid4())

DATOS = {
    "id_asegurado": ASEGURADO,
    "product_type": "auto",
    "coverage": {"plan": "todo_riesgo", "suma_asegurada": 80000000, "deducible": 1000000},
    "premium": "1200000.00",
    "effective_date": "2026-01-01",
    "expiry_date": "2026-12-31",
    "beneficiarios": [{"nombre": "Luis", "identificacion": "123", "relacion": "hijo", "porcentaje": "100"}],
}


@mock.patch("polizas.views.publicar")
@mock.patch("polizas.views.get_json", return_value={"kyc_status": "verificado"})
class PolizasTests(APITestCase):
    def emitir(self, **cambios):
        return self.client.post("/api/v1/polizas", dict(DATOS, **cambios), format="json")

    def test_emitir_y_consultar(self, get_json, publicar):
        resp = self.emitir()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["beneficiarios"]), 1)
        get_json.assert_called_once_with("POLICYHOLDER", f"/api/v1/asegurados/{ASEGURADO}")
        self.assertEqual(publicar.call_args[0][0], "policy.issued")

        resp = self.client.get(f"/api/v1/polizas/asegurado/{ASEGURADO}")
        self.assertEqual(len(resp.data), 1)

    def test_fechas_invalidas(self, get_json, publicar):
        resp = self.emitir(effective_date="2026-12-31", expiry_date="2026-01-01")
        self.assertEqual(resp.status_code, 400)

    def test_porcentajes_mayores_a_100(self, get_json, publicar):
        b = {"nombre": "A", "identificacion": "1", "relacion": "hijo", "porcentaje": "60"}
        resp = self.emitir(beneficiarios=[b, dict(b, identificacion="2")])
        self.assertEqual(resp.status_code, 400)

    def test_asegurado_no_existe(self, get_json, publicar):
        get_json.return_value = None
        resp = self.emitir()
        self.assertEqual(resp.status_code, 422)
        publicar.assert_not_called()

    def test_servicio_asegurados_caido(self, get_json, publicar):
        get_json.side_effect = ServicioNoDisponible("Circuito abierto hacia POLICYHOLDER.")
        resp = self.emitir()
        self.assertEqual(resp.status_code, 503)

    def test_cobertura_en_fecha(self, get_json, publicar):
        id = self.emitir().data["id_poliza"]
        dentro = self.client.get(f"/api/v1/polizas/{id}/cobertura?fecha=2026-06-15")
        fuera = self.client.get(f"/api/v1/polizas/{id}/cobertura?fecha=2027-02-01")
        self.assertTrue(dentro.data["vigente"])
        self.assertFalse(fuera.data["vigente"])

    def test_cotizar_tres_planes(self, get_json, publicar):
        resp = self.client.post("/api/v1/polizas/cotizar", {"product_type": "auto", "suma_asegurada": 60000000}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([c["plan"] for c in resp.data], ["basico", "estandar", "premium"])
        self.assertLess(resp.data[0]["prima_anual"], resp.data[2]["prima_anual"])

    def test_cotizar_invalido(self, get_json, publicar):
        resp = self.client.post("/api/v1/polizas/cotizar", {"product_type": "vida", "suma_asegurada": 1000, "plan": "basico", "edad": 90}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_contratar_con_plan_calcula_la_prima(self, get_json, publicar):
        cot = self.client.post("/api/v1/polizas/cotizar", {"product_type": "hogar", "suma_asegurada": 300000000, "plan": "estandar"}, format="json").data
        datos = dict(DATOS, product_type="hogar", premium="1", coverage={"plan": "estandar", "suma_asegurada": 300000000})
        datos.pop("premium")
        resp = self.client.post("/api/v1/polizas", datos, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(float(resp.data["premium"]), float(cot["prima_anual"]))
        self.assertEqual(resp.data["coverage"]["plan_nombre"], "Estándar")

    def test_renovar_y_cancelar(self, get_json, publicar):
        id = self.emitir().data["id_poliza"]
        resp = self.client.put(f"/api/v1/polizas/{id}/renovar", {"meses": 12}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "activa")

        resp = self.client.post(f"/api/v1/polizas/{id}/cancelar")
        self.assertEqual(resp.data["status"], "cancelada")
        resp = self.client.post(f"/api/v1/polizas/{id}/cancelar")
        self.assertEqual(resp.status_code, 409)
        resp = self.client.put(f"/api/v1/polizas/{id}/renovar", {}, format="json")
        self.assertEqual(resp.status_code, 409)
