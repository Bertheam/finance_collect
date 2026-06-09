from rest_framework import serializers

from accounts.models import Client
from accounts.serializers import AgentSerializer, ClientSerializer
from ledger.serializers import MouvementFinancierSerializer

from .models import Collecte, Cycle, Retenue, Retrait
from .services import get_montant_retirable


class CycleSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    agent = AgentSerializer(read_only=True)
    montant_total_collecte = serializers.SerializerMethodField()
    montant_retirable_client = serializers.SerializerMethodField()

    class Meta:
        model = Cycle
        fields = [
            "id",
            "client",
            "agent",
            "mise",
            "nb_collectes",
            "solde_actuel",
            "statut",
            "type_cloture",
            "date_cloture",
            "created_at",
            "montant_total_collecte",
            "montant_retirable_client",
        ]
        read_only_fields = fields

    def get_montant_total_collecte(self, obj):
        return obj.mise * obj.nb_collectes

    def get_montant_retirable_client(self, obj):
        return get_montant_retirable(obj.client)


class CycleCreateSerializer(serializers.Serializer):
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.select_related("agent"),
        source="client",
    )
    mise = serializers.IntegerField(min_value=1)


class DepotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collecte
        fields = ["id", "code", "cycle", "nb_mises", "montant", "created_at"]
        read_only_fields = fields


class DepotCreateSerializer(serializers.Serializer):
    nb_mises = serializers.IntegerField(min_value=1)


class RetenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Retenue
        fields = [
            "id",
            "code",
            "cycle",
            "montant",
            "commission_agent",
            "commission_institution",
            "created_at",
        ]
        read_only_fields = fields


class RetraitSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)

    class Meta:
        model = Retrait
        fields = ["id", "code", "client", "montant", "created_at"]
        read_only_fields = fields


class RetraitCreateSerializer(serializers.Serializer):
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.select_related("agent"),
        source="client",
    )
    montant = serializers.IntegerField(min_value=1)


class CycleDetailSerializer(CycleSerializer):
    retenue = RetenueSerializer(read_only=True)
    depots = DepotSerializer(many=True, read_only=True, source="collectes")
    mouvements = MouvementFinancierSerializer(many=True, read_only=True)

    class Meta(CycleSerializer.Meta):
        fields = CycleSerializer.Meta.fields + ["retenue", "depots", "mouvements"]
        read_only_fields = fields
