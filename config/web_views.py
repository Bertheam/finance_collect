from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from accounts.forms import (
    AgentForm,
    AgentUpdateForm,
    ClientForm,
    ClientUpdateForm,
    MonolithAuthenticationForm,
)
from accounts.models import Agent, Client, Notification
from accounts.services import get_visible_notifications, soft_delete_agent, soft_delete_client
from finance.forms import CycleForm, DemandeRetraitForm, DepotForm, RetraitForm
from finance.models import Cycle, DemandeRetrait
from finance.services import (
    approve_demande_retrait,
    create_cycle,
    create_demande_retrait,
    create_depot,
    create_retrait,
    cycle_is_editable,
    execute_retrait_from_demande,
    get_montant_retirable,
    reject_demande_retrait,
    soft_delete_cycle,
    update_cycle,
)
from ledger.models import MouvementFinancier


def paginate_queryset(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    querydict = request.GET.copy()
    querydict.pop("page", None)
    return {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "paginator": paginator,
        "querystring": querydict.urlencode(),
        "total_count": paginator.count,
    }


def _flatten_error_messages(value):
    if isinstance(value, ValidationError):
        if hasattr(value, "message_dict"):
            messages_list = []
            for field_errors in value.message_dict.values():
                messages_list.extend(_flatten_error_messages(field_errors))
            return messages_list
        if hasattr(value, "messages"):
            return _flatten_error_messages(value.messages)
        return [str(value)]

    if isinstance(value, dict):
        messages_list = []
        for field_errors in value.values():
            messages_list.extend(_flatten_error_messages(field_errors))
        return messages_list

    if isinstance(value, (list, tuple, set)):
        messages_list = []
        for item in value:
            messages_list.extend(_flatten_error_messages(item))
        return messages_list

    message = str(value).strip()
    return [message] if message else []


def format_exception_message(exc):
    parts = []
    seen = set()
    for message in _flatten_error_messages(exc):
        normalized = " ".join(message.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            parts.append(normalized)
    return " ".join(parts) if parts else "Une erreur est survenue."


def agent_for_user(user):
    return getattr(user, "agent_profile", None)


def client_for_user(user):
    return getattr(user, "client_profile", None)


def cycles_for_user(user):
    queryset = Cycle.objects.select_related(
        "client",
        "client__user",
        "client__agent",
        "agent",
        "agent__user",
    ).filter(
        deleted_at__isnull=True,
        client__deleted_at__isnull=True,
        agent__deleted_at__isnull=True,
    ).order_by("-created_at")

    if user.role == "ADMIN":
        return queryset

    if user.role == "AGENT":
        agent = agent_for_user(user)
        if agent is None:
            return queryset.none()
        return queryset.filter(agent=agent)

    if user.role == "CLIENT":
        client = client_for_user(user)
        if client is None:
            return queryset.none()
        return queryset.filter(client=client)

    return queryset.none()


def clients_for_user(user):
    queryset = Client.objects.select_related("user", "agent", "agent__user").filter(
        deleted_at__isnull=True,
        agent__deleted_at__isnull=True,
    ).order_by("-created_at")

    if user.role == "ADMIN":
        return queryset

    if user.role == "AGENT":
        agent = agent_for_user(user)
        if agent is None:
            return queryset.none()
        return queryset.filter(agent=agent)

    if user.role == "CLIENT":
        return queryset.filter(user=user)

    return queryset.none()


def agents_for_user(user):
    queryset = Agent.objects.select_related("user").filter(deleted_at__isnull=True).order_by("-created_at")

    if user.role == "ADMIN":
        return queryset

    if user.role == "AGENT":
        return queryset.filter(user=user)

    return queryset.none()


def mouvements_for_user(user):
    queryset = MouvementFinancier.objects.select_related("cycle", "client", "agent").filter(
        Q(client__isnull=True) | Q(client__deleted_at__isnull=True),
        Q(agent__isnull=True) | Q(agent__deleted_at__isnull=True),
        Q(cycle__isnull=True) | Q(cycle__deleted_at__isnull=True),
    ).order_by("-created_at")

    if user.role == "ADMIN":
        return queryset

    if user.role == "AGENT":
        agent = agent_for_user(user)
        if agent is None:
            return queryset.none()
        return queryset.filter(agent=agent)

    if user.role == "CLIENT":
        client = client_for_user(user)
        if client is None:
            return queryset.none()
        return queryset.filter(client=client)

    return queryset.none()


def demandes_for_user(user):
    queryset = DemandeRetrait.objects.select_related(
        "cycle",
        "cycle__agent",
        "cycle__agent__user",
        "client",
        "client__user",
        "processed_by",
        "retrait",
    ).filter(
        cycle__deleted_at__isnull=True,
        client__deleted_at__isnull=True,
        cycle__agent__deleted_at__isnull=True,
    ).order_by("-created_at")

    if user.role == "ADMIN":
        return queryset

    if user.role == "AGENT":
        agent = agent_for_user(user)
        if agent is None:
            return queryset.none()
        return queryset.filter(cycle__agent=agent)

    if user.role == "CLIENT":
        client = client_for_user(user)
        if client is None:
            return queryset.none()
        return queryset.filter(client=client)

    return queryset.none()


def commission_cycles_for_user(user):
    return (
        cycles_for_user(user)
        .filter(statut="CLOTURE", retenue__isnull=False)
        .select_related("retenue")
        .order_by("-date_cloture", "-created_at")
    )


def apply_demande_filters(request, queryset):
    q = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "").strip()
    type_demande = request.GET.get("type_demande", "").strip()

    if q:
        queryset = queryset.filter(
            Q(code__icontains=q)
            | Q(client__code_client__icontains=q)
            | Q(client__nom__icontains=q)
            | Q(client__prenom__icontains=q)
            | Q(cycle__id__icontains=q)
        )

    if statut:
        queryset = queryset.filter(statut=statut)

    if type_demande:
        queryset = queryset.filter(type_demande=type_demande)

    return queryset, {"q": q, "statut": statut, "type_demande": type_demande}


def require_staff_role(user):
    return user.role in {"ADMIN", "AGENT"}


def can_manage_client(user, client):
    if user.role == "ADMIN":
        return True
    if user.role == "AGENT":
        agent = agent_for_user(user)
        return agent is not None and client.agent_id == agent.id
    return False


def can_manage_cycle(user, cycle):
    if user.role == "ADMIN":
        return True
    if user.role == "AGENT":
        agent = agent_for_user(user)
        return agent is not None and cycle.agent_id == agent.id
    return False


def can_request_retrait(user, cycle):
    if user.role != "CLIENT":
        return False
    client = client_for_user(user)
    return client is not None and cycle.client_id == client.id


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if self.allowed_roles and request.user.role not in self.allowed_roles:
            return HttpResponseForbidden("Accès refusé.")
        return super().dispatch(request, *args, **kwargs)


def apply_client_filters(request, queryset):
    q = request.GET.get("q", "").strip()
    account_status = request.GET.get("account_status", "").strip()
    agent_id = request.GET.get("agent_id", "").strip()

    if q:
        queryset = queryset.filter(
            Q(code_client__icontains=q)
            | Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(telephone__icontains=q)
            | Q(user__username__icontains=q)
        )

    if account_status == "with_account":
        queryset = queryset.filter(user__isnull=False)
    elif account_status == "without_account":
        queryset = queryset.filter(user__isnull=True)

    if agent_id:
        queryset = queryset.filter(agent_id=agent_id)

    return queryset, {"q": q, "account_status": account_status, "agent_id": agent_id}


def apply_agent_filters(request, queryset):
    q = request.GET.get("q", "").strip()
    zone = request.GET.get("zone", "").strip()
    account_status = request.GET.get("account_status", "").strip()

    if q:
        queryset = queryset.filter(
            Q(matricule__icontains=q)
            | Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(telephone__icontains=q)
            | Q(user__username__icontains=q)
        )

    if zone:
        queryset = queryset.filter(zone__icontains=zone)

    if account_status == "with_account":
        queryset = queryset.filter(user__isnull=False)
    elif account_status == "without_account":
        queryset = queryset.filter(user__isnull=True)

    return queryset, {"q": q, "zone": zone, "account_status": account_status}


def apply_cycle_filters(request, queryset, user):
    q = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "").strip()
    agent_id = request.GET.get("agent_id", "").strip()
    client_id = request.GET.get("client_id", "").strip()

    if q:
        queryset = queryset.filter(
            Q(id__icontains=q)
            | Q(client__code_client__icontains=q)
            | Q(client__nom__icontains=q)
            | Q(client__prenom__icontains=q)
            | Q(agent__matricule__icontains=q)
        )

    if statut:
        queryset = queryset.filter(statut=statut)

    if agent_id and user.role == "ADMIN":
        queryset = queryset.filter(agent_id=agent_id)

    if client_id and user.role in {"ADMIN", "AGENT"}:
        queryset = queryset.filter(client_id=client_id)

    return queryset, {
        "q": q,
        "statut": statut,
        "agent_id": agent_id,
        "client_id": client_id,
    }


def apply_mouvement_filters(request, queryset):
    mouvement_type = request.GET.get("type_mouvement", "").strip()
    client_id = request.GET.get("client_id", "").strip()
    q = request.GET.get("q", "").strip()

    if mouvement_type:
        queryset = queryset.filter(type_mouvement=mouvement_type)

    if client_id:
        queryset = queryset.filter(client_id=client_id)

    if q:
        queryset = queryset.filter(
            Q(client__code_client__icontains=q)
            | Q(client__nom__icontains=q)
            | Q(agent__matricule__icontains=q)
            | Q(cycle__id__icontains=q)
        )

    return queryset, {"type_mouvement": mouvement_type, "client_id": client_id, "q": q}


def apply_commission_filters(request, queryset, user):
    q = request.GET.get("q", "").strip()
    agent_id = request.GET.get("agent_id", "").strip()
    client_id = request.GET.get("client_id", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if q:
        queryset = queryset.filter(
            Q(id__icontains=q)
            | Q(client__code_client__icontains=q)
            | Q(client__nom__icontains=q)
            | Q(client__prenom__icontains=q)
            | Q(agent__matricule__icontains=q)
        )

    if agent_id and user.role == "ADMIN":
        queryset = queryset.filter(agent_id=agent_id)

    if client_id and user.role in {"ADMIN", "AGENT"}:
        queryset = queryset.filter(client_id=client_id)

    if date_from:
        queryset = queryset.filter(date_cloture__date__gte=date_from)

    if date_to:
        queryset = queryset.filter(date_cloture__date__lte=date_to)

    return queryset, {
        "q": q,
        "agent_id": agent_id,
        "client_id": client_id,
        "date_from": date_from,
        "date_to": date_to,
    }


def build_commission_summary(queryset):
    aggregates = queryset.aggregate(
        commission_agent_total=Sum("retenue__commission_agent"),
        commission_institution_total=Sum("retenue__commission_institution"),
        retenue_totale=Sum("retenue__montant"),
    )
    return {
        "cycles_count": queryset.count(),
        "commission_agent_total": aggregates["commission_agent_total"] or 0,
        "commission_institution_total": aggregates["commission_institution_total"] or 0,
        "retenue_totale": aggregates["retenue_totale"] or 0,
    }


class MonolithLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = MonolithAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return response


class MonolithLogoutView(LogoutView):
    next_page = reverse_lazy("login")


class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return redirect(request.POST.get("next") or "dashboard")


class NotificationListView(LoginRequiredMixin, View):
    template_name = "notifications/list.html"

    def get(self, request):
        statut = request.GET.get("statut", "non_lues").strip() or "non_lues"
        queryset = get_visible_notifications(user=request.user, statut=statut)

        pagination = paginate_queryset(request, queryset, per_page=12)
        context = {
            "notifications": pagination["object_list"],
            "page_obj": pagination["page_obj"],
            "paginator": pagination["paginator"],
            "querystring": pagination["querystring"],
            "total_count": pagination["total_count"],
            "filters": {"statut": statut},
        }
        return render(request, self.template_name, context)


class NotificationReadAllView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, "Toutes les notifications ont été marquées comme lues.")
        return redirect(request.POST.get("next") or "notifications")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"
    recent_cycles_limit = 5
    recent_mouvements_limit = 5
    recent_commissions_limit = 5
    recent_clients_limit = 5

    def _admin_context(self, user):
        visible_cycles = cycles_for_user(user)
        visible_mouvements = mouvements_for_user(user)
        visible_clients = clients_for_user(user)
        visible_commission_cycles = commission_cycles_for_user(user)
        withdrawable_total = sum(get_montant_retirable(client) for client in visible_clients)
        commission_summary = build_commission_summary(visible_commission_cycles)
        top_agents = (
            agents_for_user(user)
            .annotate(
                cycles_count=Count("cycles", filter=Q(cycles__deleted_at__isnull=True), distinct=True),
                clients_count=Count("clients", filter=Q(clients__deleted_at__isnull=True), distinct=True),
            )
            .order_by("-commission_totale", "-cycles_count")[:5]
        )

        return {
            "dashboard_variant": "admin",
            "dashboard_title": "Tableau de bord administrateur",
            "dashboard_intro": "Vision consolidée des agents, clients, cycles et mouvements financiers.",
            "stats": {
                "cycles_count": visible_cycles.count(),
                "cycles_en_cours": visible_cycles.filter(statut="EN_COURS").count(),
                "clients_count": visible_clients.count(),
                "montant_total_retirable": withdrawable_total,
                "commission_agent_total": commission_summary["commission_agent_total"],
                "commission_institution_total": commission_summary["commission_institution_total"],
            },
            "recent_cycles": visible_cycles[: self.recent_cycles_limit],
            "recent_cycles_limit": self.recent_cycles_limit,
            "recent_mouvements": visible_mouvements[: self.recent_mouvements_limit],
            "recent_mouvements_limit": self.recent_mouvements_limit,
            "recent_commissions": visible_commission_cycles[: self.recent_commissions_limit],
            "recent_commissions_limit": self.recent_commissions_limit,
            "top_agents": top_agents,
        }

    def _agent_context(self, user):
        agent = agent_for_user(user)
        visible_cycles = cycles_for_user(user)
        visible_mouvements = mouvements_for_user(user)
        visible_clients = clients_for_user(user)
        visible_commission_cycles = commission_cycles_for_user(user)
        withdrawable_total = sum(get_montant_retirable(client) for client in visible_clients)
        commission_summary = build_commission_summary(visible_commission_cycles)

        return {
            "dashboard_variant": "agent",
            "dashboard_title": "Tableau de bord agent",
            "dashboard_intro": "Suivi de votre portefeuille clients, de vos cycles actifs et de votre commission.",
            "stats": {
                "clients_count": visible_clients.count(),
                "cycles_count": visible_cycles.count(),
                "cycles_en_cours": visible_cycles.filter(statut="EN_COURS").count(),
                "montant_total_retirable": withdrawable_total,
                "commission_agent_total": commission_summary["commission_agent_total"],
            },
            "agent_profile": agent,
            "recent_clients": visible_clients[: self.recent_clients_limit],
            "recent_clients_limit": self.recent_clients_limit,
            "recent_cycles": visible_cycles[: self.recent_cycles_limit],
            "recent_cycles_limit": self.recent_cycles_limit,
            "recent_mouvements": visible_mouvements[: self.recent_mouvements_limit],
            "recent_mouvements_limit": self.recent_mouvements_limit,
            "recent_commissions": visible_commission_cycles[: self.recent_commissions_limit],
            "recent_commissions_limit": self.recent_commissions_limit,
            "pending_demandes_count": DemandeRetrait.objects.filter(
                cycle__agent=agent,
                statut="EN_ATTENTE",
            ).count()
            if agent is not None
            else 0,
        }

    def _client_context(self, user):
        client = client_for_user(user)
        visible_cycles = cycles_for_user(user)
        montant_retirable = get_montant_retirable(client) if client is not None else 0

        return {
            "dashboard_variant": "client",
            "dashboard_title": "Mon espace client",
            "dashboard_intro": "Suivi de vos cycles d'épargne, de votre montant retirable et de vos retraits.",
            "stats": {
                "cycles_count": visible_cycles.count(),
                "cycles_en_cours": visible_cycles.filter(statut="EN_COURS").count(),
                "montant_total_retirable": montant_retirable,
                "retraits_count": client.retraits.count() if client is not None else 0,
            },
            "client_profile": client,
            "recent_cycles": visible_cycles[: self.recent_cycles_limit],
            "recent_cycles_limit": self.recent_cycles_limit,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.role == "ADMIN":
            context.update(self._admin_context(user))
        elif user.role == "AGENT":
            context.update(self._agent_context(user))
        else:
            context.update(self._client_context(user))
        return context


class ClientListView(RoleRequiredMixin, View):
    template_name = "clients/list.html"
    allowed_roles = ("ADMIN", "AGENT")

    def build_context(self, request, form):
        queryset, filters = apply_client_filters(request, clients_for_user(request.user))
        pagination = paginate_queryset(request, queryset)
        return {
            "clients": pagination["object_list"],
            "page_obj": pagination["page_obj"],
            "paginator": pagination["paginator"],
            "querystring": pagination["querystring"],
            "total_count": pagination["total_count"],
            "filters": filters,
            "agents_filter": agents_for_user(request.user),
            "can_create": require_staff_role(request.user),
            "form": form,
        }

    def get(self, request):
        return render(request, self.template_name, self.build_context(request, ClientForm(user=request.user)))

    def post(self, request):
        if not require_staff_role(request.user):
            return HttpResponseForbidden("Accès refusé.")

        form = ClientForm(request.POST, user=request.user)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Client créé avec succès. Code client : {client.code_client}.")
            return redirect("client-detail", pk=client.pk)

        return render(request, self.template_name, self.build_context(request, form), status=400)


class ClientDetailView(LoginRequiredMixin, TemplateView):
    template_name = "clients/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = get_object_or_404(clients_for_user(self.request.user), pk=kwargs["pk"])
        cycles = cycles_for_user(self.request.user).filter(client=client).order_by("-created_at")
        retraits = client.retraits.order_by("-created_at")
        demandes_retrait = client.demandes_retrait.select_related("cycle", "processed_by", "retrait").order_by("-created_at")

        context["client_profile"] = client
        context["cycles"] = cycles[:10]
        context["cycles_count"] = cycles.count()
        context["demandes_retrait"] = demandes_retrait[:10]
        context["demandes_retrait_count"] = demandes_retrait.count()
        context["montant_total_retirable"] = get_montant_retirable(client)
        context["retraits"] = retraits[:10]
        context["retraits_count"] = retraits.count()
        context["retrait_form"] = RetraitForm()
        context["can_withdraw"] = require_staff_role(self.request.user) and can_manage_client(self.request.user, client)
        context["can_toggle_account"] = require_staff_role(self.request.user) and can_manage_client(self.request.user, client)
        context["can_edit"] = require_staff_role(self.request.user) and can_manage_client(self.request.user, client)
        return context


class ClientUpdateView(RoleRequiredMixin, View):
    template_name = "clients/edit.html"
    allowed_roles = ("ADMIN", "AGENT")

    def get_client(self, request, pk):
        return get_object_or_404(clients_for_user(request.user), pk=pk)

    def get(self, request, pk):
        client = self.get_client(request, pk)
        form = ClientUpdateForm(instance=client, user=request.user, actor=request.user)
        return render(request, self.template_name, {"form": form, "client_profile": client})

    def post(self, request, pk):
        client = self.get_client(request, pk)
        form = ClientUpdateForm(request.POST, instance=client, user=request.user, actor=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Client modifié avec succès.")
            return redirect("client-detail", pk=client.pk)
        return render(request, self.template_name, {"form": form, "client_profile": client}, status=400)


class ClientRetraitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        client = get_object_or_404(clients_for_user(request.user), pk=pk)

        if not require_staff_role(request.user) or not can_manage_client(request.user, client):
            return HttpResponseForbidden("Accès refusé.")

        form = RetraitForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Montant de retrait invalide.")
            return redirect("client-detail", pk=client.pk)

        try:
            create_retrait(client=client, montant=form.cleaned_data["montant"])
            messages.success(request, "Retrait enregistré avec succès.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect("client-detail", pk=client.pk)


class ClientAccountToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        client = get_object_or_404(clients_for_user(request.user), pk=pk)

        if not require_staff_role(request.user) or not can_manage_client(request.user, client):
            return HttpResponseForbidden("Accès refusé.")

        if client.user is None:
            messages.error(request, "Ce client ne possède pas de compte utilisateur.")
            return redirect("client-detail", pk=client.pk)

        client.user.is_active = not client.user.is_active
        client.user.save(update_fields=["is_active"])
        status_label = "activé" if client.user.is_active else "désactivé"
        messages.success(request, f"Le compte client a été {status_label}.")
        return redirect("client-detail", pk=client.pk)


class ClientSoftDeleteView(RoleRequiredMixin, View):
    allowed_roles = ("ADMIN",)

    def post(self, request, pk):
        client = get_object_or_404(Client.objects.select_related("user", "agent"), pk=pk, deleted_at__isnull=True)

        try:
            soft_delete_client(client=client, deleted_by=request.user)
            messages.success(request, "Le client a été supprimé avec succès.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect("clients")


class AgentListView(RoleRequiredMixin, View):
    template_name = "agents/list.html"
    allowed_roles = ("ADMIN",)

    def build_context(self, request, form):
        queryset, filters = apply_agent_filters(request, agents_for_user(request.user))
        pagination = paginate_queryset(request, queryset)
        return {
            "agents": pagination["object_list"],
            "page_obj": pagination["page_obj"],
            "paginator": pagination["paginator"],
            "querystring": pagination["querystring"],
            "total_count": pagination["total_count"],
            "filters": filters,
            "can_create": request.user.role == "ADMIN",
            "form": form,
        }

    def get(self, request):
        return render(request, self.template_name, self.build_context(request, AgentForm()))

    def post(self, request):
        if request.user.role != "ADMIN":
            return HttpResponseForbidden("Accès refusé.")

        form = AgentForm(request.POST)
        if form.is_valid():
            agent = form.save()
            messages.success(request, "Agent créé avec succès.")
            return redirect("agent-detail", pk=agent.pk)

        return render(request, self.template_name, self.build_context(request, form), status=400)


class AgentDetailView(RoleRequiredMixin, TemplateView):
    template_name = "agents/detail.html"
    allowed_roles = ("ADMIN", "AGENT")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = get_object_or_404(agents_for_user(self.request.user), pk=kwargs["pk"])
        cycles = cycles_for_user(self.request.user).filter(agent=agent).order_by("-created_at")
        clients = clients_for_user(self.request.user).filter(agent=agent).order_by("-created_at")

        context["agent_profile"] = agent
        context["cycles"] = cycles[:10]
        context["cycles_count"] = cycles.count()
        context["clients"] = clients[:10]
        context["clients_count"] = clients.count()
        context["can_toggle_account"] = self.request.user.role == "ADMIN"
        context["can_edit"] = self.request.user.role == "ADMIN"
        return context


class AgentUpdateView(RoleRequiredMixin, View):
    template_name = "agents/edit.html"
    allowed_roles = ("ADMIN",)

    def get_agent(self, request, pk):
        return get_object_or_404(agents_for_user(request.user), pk=pk)

    def get(self, request, pk):
        agent = self.get_agent(request, pk)
        form = AgentUpdateForm(instance=agent, actor=request.user)
        return render(request, self.template_name, {"form": form, "agent_profile": agent})

    def post(self, request, pk):
        agent = self.get_agent(request, pk)
        form = AgentUpdateForm(request.POST, instance=agent, actor=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Agent modifié avec succès.")
            return redirect("agent-detail", pk=agent.pk)
        return render(request, self.template_name, {"form": form, "agent_profile": agent}, status=400)


class AgentAccountToggleView(RoleRequiredMixin, View):
    allowed_roles = ("ADMIN",)

    def post(self, request, pk):
        agent = get_object_or_404(Agent.objects.select_related("user"), pk=pk)

        if agent.user is None:
            messages.error(request, "Cet agent ne possède pas de compte utilisateur.")
            return redirect("agent-detail", pk=agent.pk)

        agent.user.is_active = not agent.user.is_active
        agent.user.save(update_fields=["is_active"])
        status_label = "activé" if agent.user.is_active else "désactivé"
        messages.success(request, f"Le compte agent a été {status_label}.")
        return redirect("agent-detail", pk=agent.pk)


class AgentSoftDeleteView(RoleRequiredMixin, View):
    allowed_roles = ("ADMIN",)

    def post(self, request, pk):
        agent = get_object_or_404(Agent.objects.select_related("user"), pk=pk, deleted_at__isnull=True)

        try:
            soft_delete_agent(agent=agent, deleted_by=request.user)
            messages.success(request, "L’agent a été supprimé avec succès.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect("agents")


class CycleListView(LoginRequiredMixin, View):
    template_name = "cycles/list.html"

    def build_context(self, request, form):
        queryset, filters = apply_cycle_filters(request, cycles_for_user(request.user), request.user)
        pagination = paginate_queryset(request, queryset)
        cycles = list(pagination["object_list"])
        for cycle in cycles:
            cycle.can_edit = require_staff_role(request.user) and can_manage_cycle(request.user, cycle) and cycle_is_editable(cycle)
        return {
            "cycles": cycles,
            "page_obj": pagination["page_obj"],
            "paginator": pagination["paginator"],
            "querystring": pagination["querystring"],
            "total_count": pagination["total_count"],
            "filters": filters,
            "agents_filter": agents_for_user(request.user),
            "clients_filter": clients_for_user(request.user),
            "can_create": require_staff_role(request.user),
            "form": form,
        }

    def get(self, request):
        return render(request, self.template_name, self.build_context(request, CycleForm(user=request.user)))

    def post(self, request):
        if not require_staff_role(request.user):
            return HttpResponseForbidden("Accès refusé.")

        form = CycleForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                cycle = create_cycle(client=form.cleaned_data["client"], mise=form.cleaned_data["mise"])
                messages.success(request, "Cycle créé avec succès.")
                return redirect("cycle-detail", pk=cycle.pk)
            except Exception as exc:
                form.add_error(None, format_exception_message(exc))

        return render(request, self.template_name, self.build_context(request, form), status=400)


class CycleDetailView(LoginRequiredMixin, TemplateView):
    template_name = "cycles/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = get_object_or_404(cycles_for_user(self.request.user), pk=kwargs["pk"])
        context["cycle"] = cycle
        context["depot_form"] = DepotForm(initial={"nb_mises": 1})
        context["demande_retrait_form"] = DemandeRetraitForm()
        context["retrait_direct_form"] = RetraitForm()
        context["depots"] = cycle.collectes.order_by("-created_at")
        context["demandes_retrait"] = cycle.demandes_retrait.order_by("-created_at")[:10]
        context["mouvements"] = cycle.mouvements.order_by("-created_at")
        context["retenue"] = getattr(cycle, "retenue", None)
        context["can_operate"] = can_manage_cycle(self.request.user, cycle)
        context["can_direct_withdraw"] = require_staff_role(self.request.user) and can_manage_cycle(self.request.user, cycle)
        context["can_manage_demandes"] = can_manage_cycle(self.request.user, cycle)
        context["can_edit"] = require_staff_role(self.request.user) and can_manage_cycle(self.request.user, cycle) and cycle_is_editable(cycle)
        context["can_request_retrait"] = can_request_retrait(self.request.user, cycle)
        context["montant_total_collecte"] = cycle.mise * cycle.nb_collectes
        context["montant_total_retirable"] = get_montant_retirable(cycle.client)
        context["cycle_secondary_metric_label"] = "Crédit client" if cycle.statut == "CLOTURE" else "Retenue prévue"
        context["cycle_secondary_metric_value"] = cycle.solde_actuel if cycle.statut == "CLOTURE" else cycle.mise
        return context


class CycleUpdateView(RoleRequiredMixin, View):
    template_name = "cycles/edit.html"
    allowed_roles = ("ADMIN", "AGENT")

    def get_cycle(self, request, pk):
        return get_object_or_404(cycles_for_user(request.user), pk=pk)

    def get(self, request, pk):
        cycle = self.get_cycle(request, pk)
        if not can_manage_cycle(request.user, cycle):
            return HttpResponseForbidden("Accès refusé.")
        if not cycle_is_editable(cycle):
            messages.error(request, "Ce cycle ne peut plus être modifié.")
            return redirect("cycle-detail", pk=cycle.pk)

        form = CycleForm(instance=cycle, user=request.user)
        return render(request, self.template_name, {"form": form, "cycle": cycle})

    def post(self, request, pk):
        cycle = self.get_cycle(request, pk)
        if not can_manage_cycle(request.user, cycle):
            return HttpResponseForbidden("Accès refusé.")

        form = CycleForm(request.POST, instance=cycle, user=request.user)
        if form.is_valid():
            try:
                update_cycle(cycle=cycle, client=form.cleaned_data["client"], mise=form.cleaned_data["mise"])
                messages.success(request, "Cycle modifié avec succès.")
                return redirect("cycle-detail", pk=cycle.pk)
            except Exception as exc:
                form.add_error(None, format_exception_message(exc))

        return render(request, self.template_name, {"form": form, "cycle": cycle}, status=400)


class CycleDepotView(LoginRequiredMixin, View):
    def post(self, request, pk):
        cycle = get_object_or_404(cycles_for_user(request.user), pk=pk)

        if not require_staff_role(request.user):
            return HttpResponseForbidden("Accès refusé.")

        if request.user.role == "AGENT":
            agent = agent_for_user(request.user)
            if agent is None or cycle.agent_id != agent.id:
                return HttpResponseForbidden("Ce cycle n’appartient pas à cet agent.")

        form = DepotForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Nombre de mises invalide.")
            return redirect("cycle-detail", pk=cycle.pk)

        try:
            create_depot(cycle=cycle, nb_mises=form.cleaned_data["nb_mises"])
            messages.success(request, "Dépôt enregistré avec succès.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect("cycle-detail", pk=cycle.pk)


class CycleDemandeRetraitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        cycle = get_object_or_404(cycles_for_user(request.user), pk=pk)

        form = DemandeRetraitForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Demande de retrait invalide.")
            return redirect("cycle-detail", pk=cycle.pk)

        type_demande = form.cleaned_data["type_demande"]
        is_client_owner = can_request_retrait(request.user, cycle)
        is_staff_anticipatory = can_manage_cycle(request.user, cycle) and type_demande == "ANTICIPE"

        if not is_client_owner and not is_staff_anticipatory:
            return HttpResponseForbidden("Accès refusé.")

        try:
            create_demande_retrait(
                cycle=cycle,
                type_demande=type_demande,
                montant_souhaite=form.cleaned_data.get("montant_souhaite"),
                motif=form.cleaned_data.get("motif", ""),
                created_by=request.user,
            )
            messages.success(request, "La demande de retrait a été enregistrée.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect("cycle-detail", pk=cycle.pk)


class CycleDirectRetraitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        cycle = get_object_or_404(cycles_for_user(request.user), pk=pk)

        if not require_staff_role(request.user) or not can_manage_cycle(request.user, cycle):
            return HttpResponseForbidden("Accès refusé.")

        form = RetraitForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Montant de retrait invalide.")
            return redirect("cycle-detail", pk=cycle.pk)

        try:
            create_retrait(client=cycle.client, montant=form.cleaned_data["montant"])
            messages.success(request, "Retrait direct enregistré avec succès.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect("cycle-detail", pk=cycle.pk)


class CycleSoftDeleteView(RoleRequiredMixin, View):
    allowed_roles = ("ADMIN",)

    def post(self, request, pk):
        cycle = get_object_or_404(Cycle.objects.select_related("client", "agent"), pk=pk, deleted_at__isnull=True)

        try:
            soft_delete_cycle(cycle=cycle, deleted_by=request.user)
            messages.success(request, "Le cycle a été supprimé avec succès.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect("cycles")


class DemandeRetraitApproveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        demande = get_object_or_404(
            DemandeRetrait.objects.select_related("cycle", "client"),
            pk=pk,
        )

        if not can_manage_cycle(request.user, demande.cycle):
            return HttpResponseForbidden("Accès refusé.")

        try:
            approve_demande_retrait(demande=demande, processed_by=request.user)
            messages.success(request, "La demande de retrait a été validée.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect(request.POST.get("next") or reverse_lazy("cycle-detail", kwargs={"pk": demande.cycle_id}))


class DemandeRetraitRejectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        demande = get_object_or_404(
            DemandeRetrait.objects.select_related("cycle", "client"),
            pk=pk,
        )

        if not can_manage_cycle(request.user, demande.cycle):
            return HttpResponseForbidden("Accès refusé.")

        try:
            reject_demande_retrait(demande=demande, processed_by=request.user)
            messages.success(request, "La demande de retrait a été rejetée.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect(request.POST.get("next") or reverse_lazy("cycle-detail", kwargs={"pk": demande.cycle_id}))


class DemandeRetraitExecuteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        demande = get_object_or_404(
            DemandeRetrait.objects.select_related("cycle", "client"),
            pk=pk,
        )

        if not can_manage_cycle(request.user, demande.cycle):
            return HttpResponseForbidden("Accès refusé.")

        try:
            execute_retrait_from_demande(demande=demande, processed_by=request.user)
            messages.success(request, "Le retrait lié à la demande a été exécuté.")
        except Exception as exc:
            messages.error(request, format_exception_message(exc))

        return redirect(request.POST.get("next") or reverse_lazy("cycle-detail", kwargs={"pk": demande.cycle_id}))


class DemandeRetraitListView(RoleRequiredMixin, View):
    template_name = "demandes/list.html"
    allowed_roles = ("ADMIN", "AGENT")

    def get(self, request):
        queryset, filters = apply_demande_filters(request, demandes_for_user(request.user))
        pagination = paginate_queryset(request, queryset, per_page=12)
        context = {
            "demandes": pagination["object_list"],
            "page_obj": pagination["page_obj"],
            "paginator": pagination["paginator"],
            "querystring": pagination["querystring"],
            "total_count": pagination["total_count"],
            "filters": filters,
        }
        return render(request, self.template_name, context)


class CommissionCycleListView(RoleRequiredMixin, View):
    template_name = "commissions/list.html"
    allowed_roles = ("ADMIN", "AGENT")

    def get(self, request):
        queryset, filters = apply_commission_filters(
            request,
            commission_cycles_for_user(request.user),
            request.user,
        )
        summary = build_commission_summary(queryset)
        pagination = paginate_queryset(request, queryset, per_page=12)
        context = {
            "commission_cycles": pagination["object_list"],
            "page_obj": pagination["page_obj"],
            "paginator": pagination["paginator"],
            "querystring": pagination["querystring"],
            "total_count": pagination["total_count"],
            "filters": filters,
            "summary": summary,
            "agents_filter": agents_for_user(request.user),
            "clients_filter": clients_for_user(request.user),
        }
        return render(request, self.template_name, context)


class MyClientSpaceView(LoginRequiredMixin, View):
    def get(self, request):
        client = client_for_user(request.user)
        if request.user.role != "CLIENT" or client is None:
            return HttpResponseForbidden("Accès refusé.")
        return redirect("client-detail", pk=client.pk)


class MouvementListView(RoleRequiredMixin, View):
    template_name = "mouvements/list.html"
    allowed_roles = ("ADMIN", "AGENT")

    def get(self, request):
        queryset, filters = apply_mouvement_filters(request, mouvements_for_user(request.user))
        pagination = paginate_queryset(request, queryset, per_page=15)
        context = {
            "mouvements": pagination["object_list"],
            "page_obj": pagination["page_obj"],
            "paginator": pagination["paginator"],
            "querystring": pagination["querystring"],
            "total_count": pagination["total_count"],
            "filters": filters,
            "clients_filter": clients_for_user(request.user),
            "type_choices": MouvementFinancier.TYPE_MOUVEMENTS,
        }
        return render(request, self.template_name, context)
