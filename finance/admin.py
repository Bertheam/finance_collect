from django.contrib import admin

from .models import Collecte, Cycle, Retenue, Retrait


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
