"""Pruebas unitarias: una unidad de lógica de negocio aislada; las dependencias externas se simulan con mocks."""
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase

from comun.clientes import ServicioNoDisponible
from polizas.cotizador import CotizacionInvalida, cotizar


class CotizadorUnitTests(SimpleTestCase):
    def test_vida_aplica_recargo_por_edad_y_cuota_mensual(self):
        joven = cotizar("vida", 100000000, "estandar", edad=25)
        mayor = cotizar("vida", 100000000, "estandar", edad=55)
        self.assertGreater(mayor["prima_anual"], joven["prima_anual"])
        self.assertEqual(mayor["prima_mensual"] % 1000, 0)
        self.assertLessEqual(abs(mayor["prima_mensual"] * 12 - mayor["prima_anual"]), Decimal("6000"))
        with self.assertRaises(CotizacionInvalida):
            cotizar("vida", 100000000, "estandar", edad=80)


class EmisionUnitTests(TestCase):
    @mock.patch("polizas.views.publicar")
    @mock.patch("polizas.views.get_json", side_effect=ServicioNoDisponible("Circuito abierto hacia POLICYHOLDER."))
    def test_no_emite_si_asegurados_no_responde(self, get_json, publicar):
        datos = {"id_asegurado": "8f1c2a3b-0000-4000-8000-000000000001", "product_type": "auto",
                 "coverage": {"plan": "estandar", "suma_asegurada": 60000000},
                 "effective_date": "2026-01-01", "expiry_date": "2026-12-31"}
        resp = self.client.post("/api/v1/polizas", datos, content_type="application/json")
        self.assertEqual(resp.status_code, 503)
        publicar.assert_not_called()  # sin validación del asegurado no se emite ni se publica el evento
