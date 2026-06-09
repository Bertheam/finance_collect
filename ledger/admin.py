from django.contrib import admin

from .models import MouvementFinancier


@admin.register(MouvementFinancier)
class MouvementFinancierAdmin(admin.ModelAdmin):
    list_display = ("id", "type_mouvement", "client", "agent", "cycle", "montant", "created_at")
    list_filter = ("type_mouvement", "source", "destination")
    search_fields = ("client__code_client", "agent__matricule", "cycle__id")
