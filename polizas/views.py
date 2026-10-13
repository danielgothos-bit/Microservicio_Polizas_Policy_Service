import calendar
import logging
from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from comun.clientes import ServicioNoDisponible, get_json
from comun.eventos import publicar

from .cotizador import PLANES, CotizacionInvalida, cotizar, todas
from .models import Poliza
from .serializers import PolizaSerializer, RenovarSerializer

logger = logging.getLogger(__name__)


def error(code, message, http_status):
    return Response({"code": code, "message": message}, status=http_status)


def sumar_meses(fecha, meses):
    mes = fecha.month - 1 + meses
    anio, mes = fecha.year + mes // 12, mes % 12 + 1
    return fecha.replace(year=anio, month=mes, day=min(fecha.day, calendar.monthrange(anio, mes)[1]))


def datos_evento(poliza):
    return {
        "id_poliza": poliza.id_poliza,
        "id_asegurado": poliza.id_asegurado,
        "product_type": poliza.product_type,
        "premium": poliza.premium,
        "status": poliza.status,
        "effective_date": poliza.effective_date,
        "expiry_date": poliza.expiry_date,
    }


@api_view(["GET", "POST"])
def polizas(request):
    if request.method == "GET":
        qs = Poliza.objects.prefetch_related("beneficiarios").order_by("-created_at")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response(PolizaSerializer(qs, many=True).data)

    serializer = PolizaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Validación síncrona de identidad contra el Policyholder Service (sección 4.1).
    id_asegurado = serializer.validated_data["id_asegurado"]
    try:
        asegurado = get_json("POLICYHOLDER", f"/api/v1/asegurados/{id_asegurado}")
    except ServicioNoDisponible as exc:
        if "no está configurada" in str(exc):
            logger.warning("validación de asegurado omitida (modo aislado)")
            asegurado = {"kyc_status": "pendiente"}
        else:
            return error("SERVICE_UNAVAILABLE", "El servicio de Asegurados no está disponible.", status.HTTP_503_SERVICE_UNAVAILABLE)

    if asegurado is None:
        return error("ASEGURADO_NOT_FOUND", "El asegurado no existe.", status.HTTP_422_UNPROCESSABLE_ENTITY)
    if asegurado.get("kyc_status") == "rechazado":
        return error("KYC_REJECTED", "La verificación de identidad del asegurado fue rechazada.", status.HTTP_422_UNPROCESSABLE_ENTITY)

    poliza = serializer.save()
    publicar("policy.issued", datos_evento(poliza))
    return Response(PolizaSerializer(poliza).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def cotizar_poliza(request):
    """Cotiza un producto: con `plan` devuelve ese plan; sin `plan`, los tres para comparar."""
    datos = request.data
    try:
        if datos.get("plan"):
            resultado = cotizar(datos.get("product_type"), datos.get("suma_asegurada", 0), datos["plan"], datos.get("edad"))
        else:
            if datos.get("product_type") not in PLANES:
                raise CotizacionInvalida("Producto no disponible.")
            resultado = todas(datos["product_type"], datos.get("suma_asegurada", 0), datos.get("edad"))
    except (CotizacionInvalida, ArithmeticError, TypeError) as exc:
        return error("VALIDATION_ERROR", str(exc) or "Datos de cotización inválidos.", status.HTTP_400_BAD_REQUEST)
    return Response(resultado)


@api_view(["GET"])
def productos(request):
    """Catálogo de productos y planes (sin precios)."""
    return Response({k: {"nombre": v["nombre"], "valor": v["valor"],
                         "planes": {p: {"nombre": i["nombre"], "coberturas": i["coberturas"]} for p, i in v["planes"].items()}}
                     for k, v in PLANES.items()})


@api_view(["GET"])
def poliza_detalle(request, id):
    poliza = get_object_or_404(Poliza, id_poliza=id)
    poliza.actualizar_vencimiento()
    data = PolizaSerializer(poliza).data
    data["cobertura_vigente"] = poliza.cubre(date.today())
    return Response(data)


@api_view(["GET"])
def poliza_cobertura(request, id):
    """Consulta de cobertura en una fecha (?fecha=AAAA-MM-DD). La usa Siniestros."""
    poliza = get_object_or_404(Poliza, id_poliza=id)
    poliza.actualizar_vencimiento()

    try:
        fecha = date.fromisoformat(request.query_params.get("fecha", date.today().isoformat())[:10])
    except ValueError:
        return error("VALIDATION_ERROR", "fecha debe tener formato AAAA-MM-DD.", status.HTTP_400_BAD_REQUEST)

    return Response({
        "id_poliza": poliza.id_poliza,
        "id_asegurado": poliza.id_asegurado,
        "fecha": fecha,
        "vigente": poliza.cubre(fecha),
        "status": poliza.status,
        "product_type": poliza.product_type,
        "coverage": poliza.coverage,
        "premium": poliza.premium,
        "effective_date": poliza.effective_date,
        "expiry_date": poliza.expiry_date,
    })


@api_view(["PUT"])
def poliza_renovar(request, id):
    poliza = get_object_or_404(Poliza, id_poliza=id)
    if poliza.status == Poliza.CANCELADA:
        return error("POLICY_CANCELLED", "Una póliza cancelada no se puede renovar.", status.HTTP_409_CONFLICT)

    serializer = RenovarSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    inicio = max(poliza.expiry_date, date.today())
    poliza.expiry_date = sumar_meses(inicio, serializer.validated_data["meses"])
    if "premium" in serializer.validated_data:
        poliza.premium = serializer.validated_data["premium"]
    poliza.status = Poliza.ACTIVA
    poliza.save()

    publicar("policy.renewed", datos_evento(poliza))
    return Response(PolizaSerializer(poliza).data)


@api_view(["POST"])
def poliza_cancelar(request, id):
    poliza = get_object_or_404(Poliza, id_poliza=id)
    if poliza.status == Poliza.CANCELADA:
        return error("ALREADY_CANCELLED", "La póliza ya está cancelada.", status.HTTP_409_CONFLICT)

    poliza.status = Poliza.CANCELADA
    poliza.save(update_fields=["status"])

    publicar("policy.cancelled", datos_evento(poliza))
    return Response(PolizaSerializer(poliza).data)


@api_view(["GET"])
def polizas_por_asegurado(request, id):
    qs = Poliza.objects.filter(id_asegurado=id).prefetch_related("beneficiarios").order_by("-created_at")
    for poliza in qs:
        poliza.actualizar_vencimiento()
    return Response(PolizaSerializer(qs, many=True).data)
