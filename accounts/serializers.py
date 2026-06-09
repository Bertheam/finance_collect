from rest_framework import serializers

from .models import Agent, Client, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
            "mfa_enabled",
            "is_active",
        ]
        read_only_fields = fields


class AgentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ["id", "matricule", "nom", "prenom", "telephone", "zone"]
        read_only_fields = fields


class ClientSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "code_client", "nom", "prenom", "telephone"]
        read_only_fields = fields


class AgentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Agent
        fields = [
            "id",
            "matricule",
            "nom",
            "prenom",
            "telephone",
            "zone",
            "commission_totale",
            "created_at",
            "user",
        ]
        read_only_fields = fields


class ClientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    agent = AgentSummarySerializer(read_only=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "code_client",
            "nom",
            "prenom",
            "telephone",
            "email",
            "adresse",
            "created_at",
            "agent",
            "user",
        ]
        read_only_fields = fields
