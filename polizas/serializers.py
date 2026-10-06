from rest_framework import serializers

from .models import Beneficiario, Poliza


class BeneficiarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Beneficiario
        fields = ["id_beneficiario", "nombre", "identificacion", "relacion", "porcentaje"]
        read_only_fields = ["id_beneficiario"]

    def validate_porcentaje(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("El porcentaje debe estar entre 0 y 100.")
        return value


class PolizaSerializer(serializers.ModelSerializer):
    beneficiarios = BeneficiarioSerializer(many=True, required=False)

    class Meta:
        model = Poliza
        fields = [
            "id_poliza",
            "id_asegurado",
            "product_type",
            "coverage",
            "premium",
            "status",
            "effective_date",
            "expiry_date",
            "created_at",
            "beneficiarios",
        ]
        read_only_fields = ["id_poliza", "status", "created_at"]

    def validate_premium(self, value):
        if value < 0:
            raise serializers.ValidationError("La prima no puede ser negativa.")
        return value

    def validate(self, data):
        if data["effective_date"] >= data["expiry_date"]:
            raise serializers.ValidationError({"expiry_date": "Debe ser posterior a effective_date."})
        total = sum(b["porcentaje"] for b in data.get("beneficiarios", []))
        if total > 100:
            raise serializers.ValidationError({"beneficiarios": "La suma de porcentajes no puede superar 100."})
        return data

    def create(self, validated_data):
        beneficiarios = validated_data.pop("beneficiarios", [])
        poliza = Poliza.objects.create(**validated_data)
        for b in beneficiarios:
            Beneficiario.objects.create(poliza=poliza, **b)
        return poliza


class RenovarSerializer(serializers.Serializer):
    meses = serializers.IntegerField(min_value=1, max_value=60, default=12)
    premium = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
