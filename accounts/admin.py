from django.contrib import admin

from .models import Agent, Client, Notification, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "telephone", "role", "is_active")
    list_filter = ("role", "is_active", "mfa_enabled")
    search_fields = ("username", "telephone", "first_name", "last_name", "email")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("matricule", "prenom", "nom", "telephone", "zone", "commission_totale")
    search_fields = ("matricule", "prenom", "nom", "telephone", "zone")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("code_client", "prenom", "nom", "telephone", "agent")
    list_filter = ("agent",)
    search_fields = ("code_client", "prenom", "nom", "telephone", "email")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("title", "message", "user__username")
