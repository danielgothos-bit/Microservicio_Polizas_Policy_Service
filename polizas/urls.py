from django.urls import path

from . import views

urlpatterns = [
    path("api/v1/polizas", views.polizas),
    path("api/v1/polizas/cotizar", views.cotizar_poliza),
    path("api/v1/polizas/productos", views.productos),
    path("api/v1/polizas/<uuid:id>", views.poliza_detalle),
    path("api/v1/polizas/<uuid:id>/cobertura", views.poliza_cobertura),
    path("api/v1/polizas/<uuid:id>/renovar", views.poliza_renovar),
    path("api/v1/polizas/<uuid:id>/cancelar", views.poliza_cancelar),
    path("api/v1/polizas/asegurado/<uuid:id>", views.polizas_por_asegurado),
]
