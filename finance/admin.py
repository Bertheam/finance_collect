from django.contrib import admin

from .models import Collecte, Cycle, DemandeRetrait, Retenue, Retrait


@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "agent", "mise", "nb_collectes", "statut", "type_cloture")
    list_filter = ("statut", "type_cloture", "agent")
    search_fields = ("id", "client__code_client", "client__nom", "agent__matricule")


@admin.register(Collecte)
class CollecteAdmin(admin.ModelAdmin):
    list_display = ("code", "cycle", "nb_mises", "montant", "created_at")
    list_filter = ("created_at",)
    search_fields = ("code", "cycle__id", "cycle__client__code_client")


@admin.register(Retenue)
class RetenueAdmin(admin.ModelAdmin):
    list_display = ("code", "cycle", "montant", "commission_agent", "commission_institution")
    search_fields = ("code", "cycle__id", "cycle__client__code_client")


@admin.register(Retrait)
class RetraitAdmin(admin.ModelAdmin):
    list_display = ("code", "client", "montant", "created_at")
    list_filter = ("created_at",)
    search_fields = ("code", "client__code_client", "client__nom", "client__prenom")


@admin.register(DemandeRetrait)
class DemandeRetraitAdmin(admin.ModelAdmin):
    list_display = ("code", "cycle", "client", "type_demande", "statut", "montant_souhaite", "processed_at", "created_at")
    list_filter = ("type_demande", "statut", "created_at")
    search_fields = ("code", "client__code_client", "client__nom", "client__prenom", "cycle__id")
