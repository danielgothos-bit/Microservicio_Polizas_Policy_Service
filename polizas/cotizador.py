"""
Cotizador de primas por línea de negocio y plan.

La prima anual se calcula como un porcentaje del valor asegurado (tasa por plan),
con una prima mínima por producto. En vida la tasa aumenta con la edad.
"""
from decimal import ROUND_HALF_UP, Decimal

PLANES = {
    "auto": {
        "nombre": "Seguro de Auto",
        "valor": "Valor comercial del vehículo",
        "minima": Decimal("650000"),
        "planes": {
            "basico": {"nombre": "Básico", "tasa": Decimal("0.030"),
                       "coberturas": ["Responsabilidad civil extracontractual", "Pérdida total por hurto",
                                      "Asistencia en carretera"]},
            "estandar": {"nombre": "Estándar", "tasa": Decimal("0.042"),
                         "coberturas": ["Todo lo del plan Básico", "Pérdida parcial por daños",
                                        "Pérdida total por daños", "Vehículo de reemplazo 10 días"]},
            "premium": {"nombre": "Premium", "tasa": Decimal("0.055"),
                        "coberturas": ["Todo lo del plan Estándar", "Deducible cero en pérdidas parciales",
                                       "Conductor elegido", "Vehículo de reemplazo 30 días"]},
        },
    },
    "hogar": {
        "nombre": "Seguro de Hogar",
        "valor": "Valor de la vivienda y sus contenidos",
        "minima": Decimal("320000"),
        "planes": {
            "basico": {"nombre": "Básico", "tasa": Decimal("0.0025"),
                       "coberturas": ["Incendio y rayo", "Terremoto", "Asistencia domiciliaria"]},
            "estandar": {"nombre": "Estándar", "tasa": Decimal("0.0035"),
                         "coberturas": ["Todo lo del plan Básico", "Hurto calificado", "Daños por agua",
                                        "Responsabilidad civil familiar"]},
            "premium": {"nombre": "Premium", "tasa": Decimal("0.0050"),
                        "coberturas": ["Todo lo del plan Estándar", "Equipos electrónicos",
                                       "Gastos de arrendamiento temporal", "Asistencia para mascotas"]},
        },
    },
    "vida": {
        "nombre": "Seguro de Vida",
        "valor": "Suma asegurada para tus beneficiarios",
        "minima": Decimal("180000"),
        "planes": {
            "basico": {"nombre": "Básico", "tasa": Decimal("0.0040"),
                       "coberturas": ["Muerte por cualquier causa", "Auxilio funerario"]},
            "estandar": {"nombre": "Estándar", "tasa": Decimal("0.0052"),
                         "coberturas": ["Todo lo del plan Básico", "Incapacidad total y permanente",
                                        "Enfermedades graves"]},
            "premium": {"nombre": "Premium", "tasa": Decimal("0.0064"),
                        "coberturas": ["Todo lo del plan Estándar", "Renta diaria por hospitalización",
                                       "Orientación médica telefónica 24/7"]},
        },
    },
}


class CotizacionInvalida(ValueError):
    pass


def _redondear(valor):
    return (valor / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 1000


def cotizar(product_type, suma_asegurada, plan, edad=None):
    producto = PLANES.get(product_type)
    if producto is None:
        raise CotizacionInvalida("Producto no disponible.")
    info = producto["planes"].get(plan)
    if info is None:
        raise CotizacionInvalida("Plan no disponible.")

    suma = Decimal(str(suma_asegurada))
    if suma <= 0:
        raise CotizacionInvalida("El valor asegurado debe ser mayor que 0.")

    tasa = info["tasa"]
    if product_type == "vida":
        edad = int(edad or 30)
        if not 18 <= edad <= 75:
            raise CotizacionInvalida("La edad debe estar entre 18 y 75 años.")
        tasa = tasa * (1 + Decimal(max(0, edad - 25)) * Decimal("0.035"))

    anual = max(_redondear(suma * tasa), producto["minima"])
    return {
        "product_type": product_type,
        "producto": producto["nombre"],
        "plan": plan,
        "plan_nombre": info["nombre"],
        "suma_asegurada": suma,
        "prima_anual": anual,
        "prima_mensual": _redondear(anual / 12),
        "coberturas": info["coberturas"],
    }


def todas(product_type, suma_asegurada, edad=None):
    """Cotiza los tres planes de un producto (para compararlos)."""
    return [cotizar(product_type, suma_asegurada, plan, edad) for plan in PLANES[product_type]["planes"]]
