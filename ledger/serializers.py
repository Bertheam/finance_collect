from rest_framework import serializers

from .models import MouvementFinancier


class MouvementFinancierSerializer(serializers.ModelSerializer):
    class Meta:
        model = MouvementFinancier
        fields = [
            "id",
            "cycle",
            "client",
            "agent",
            "type_mouvement",
            "source",
            "destination",
            "montant",
            "created_at",
        ]
        read_only_fields = fields
