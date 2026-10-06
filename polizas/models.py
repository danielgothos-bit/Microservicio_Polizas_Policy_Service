import uuid
from datetime import date

from django.db import models
from django.db.models import F, Q


class Poliza(models.Model):
    AUTO, HOGAR, VIDA = "auto", "hogar", "vida"
    PRODUCT_CHOICES = [(AUTO, "Auto"), (HOGAR, "Hogar"), (VIDA, "Vida")]

    ACTIVA, VENCIDA, CANCELADA = "activa", "vencida", "cancelada"
    STATUS_CHOICES = [(ACTIVA, "Activa"), (VENCIDA, "Vencida"), (CANCELADA, "Cancelada")]

    id_poliza = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id_asegurado = models.UUIDField()  # FK-ext -> Policyholder Service
    product_type = models.CharField(max_length=10, choices=PRODUCT_CHOICES)
    coverage = models.JSONField(default=dict)  # JSONB en PostgreSQL
    premium = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVA)
    effective_date = models.DateField()
    expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "poliza"
        indexes = [
            models.Index(fields=["id_asegurado"], name="idx_poliza_asegurado"),
            models.Index(fields=["status"], name="idx_poliza_status"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(product_type__in=["auto", "hogar", "vida"]), name="chk_poliza_product_type"),
            models.CheckConstraint(condition=Q(status__in=["activa", "vencida", "cancelada"]), name="chk_poliza_status"),
            models.CheckConstraint(condition=Q(effective_date__lt=F("expiry_date")), name="chk_poliza_fechas"),
            models.CheckConstraint(condition=Q(premium__gte=0), name="chk_poliza_premium"),
        ]

    def actualizar_vencimiento(self):
        """Marca la póliza como vencida si ya pasó su fecha de expiración."""
        if self.status == self.ACTIVA and self.expiry_date < date.today():
            self.status = self.VENCIDA
            self.save(update_fields=["status"])

    def cubre(self, fecha):
        """¿Existía cobertura vigente en esa fecha? (validación usada por Siniestros)."""
        return self.status != self.CANCELADA and self.effective_date <= fecha <= self.expiry_date

    def __str__(self):
        return f"Póliza {self.id_poliza} - {self.product_type}"


class Beneficiario(models.Model):
    id_beneficiario = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poliza = models.ForeignKey(Poliza, on_delete=models.CASCADE, related_name="beneficiarios", db_column="id_poliza")
    nombre = models.CharField(max_length=150)
    identificacion = models.CharField(max_length=30)
    relacion = models.CharField(max_length=50)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = "beneficiario"
        indexes = [
            models.Index(fields=["poliza"], name="idx_beneficiario_poliza"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(porcentaje__gte=0, porcentaje__lte=100), name="chk_beneficiario_porcentaje"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.porcentaje}%)"
