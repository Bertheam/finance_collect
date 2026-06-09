from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from accounts.forms import AgentForm, ClientForm, MonolithAuthenticationForm
from accounts.models import Agent, Client
from finance.forms import CycleForm, DepotForm, RetraitForm
from finance.models import Cycle
from finance.services import create_cycle, create_depot, create_retrait, get_montant_retirable
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
    queryset = Client.objects.select_related("user", "agent", "agent__user").order_by("-created_at")

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
    queryset = Agent.objects.select_related("user").order_by("-created_at")

    if user.role == "ADMIN":
        return queryset

    if user.role == "AGENT":
        return queryset.filter(user=user)

    return queryset.none()


def mouvements_for_user(user):
    queryset = MouvementFinancier.objects.select_related("cycle", "client", "agent").order_by("-created_at")

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


def require_staff_role(user):
    return user.role in {"ADMIN", "AGENT"}


def can_manage_client(user, client):
    if user.role == "ADMIN":
        return True
    if user.role == "AGENT":
        agent = agent_for_user(user)
        return agent is not None and client.agent_id == agent.id
    return False


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


class MonolithLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = MonolithAuthenticationForm
    redirect_authenticated_user = True


class MonolithLogoutView(LogoutView):
    next_page = reverse_lazy("login")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        visible_cycles = cycles_for_user(user)
        visible_mouvements = mouvements_for_user(user)
        visible_clients = clients_for_user(user)
        withdrawable_total = sum(get_montant_retirable(client) for client in visible_clients)

        context["stats"] = {
            "cycles_count": visible_cycles.count(),
            "cycles_en_cours": visible_cycles.filter(statut="EN_COURS").count(),
            "clients_count": visible_clients.count(),
            "montant_total_retirable": withdrawable_total,
        }
        context["recent_cycles"] = visible_cycles[:5]
        context["recent_mouvements"] = visible_mouvements[:8]
        context["top_agents"] = (
            agents_for_user(user)
            .annotate(cycles_count=Count("cycles"), clients_count=Count("clients", distinct=True))
            .order_by("-commission_totale", "-cycles_count")[:5]
        )
        return context


class ClientListView(LoginRequiredMixin, View):
    template_name = "clients/list.html"

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
            return HttpResponseForbidden("Acces refuse.")

        form = ClientForm(request.POST, user=request.user)
        if form.is_valid():
            client = form.save()
            messages.success(request, "Client cree avec succes.")
            return redirect("client-detail", pk=client.pk)

        return render(request, self.template_name, self.build_context(request, form), status=400)


class ClientDetailView(LoginRequiredMixin, TemplateView):
    template_name = "clients/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = get_object_or_404(clients_for_user(self.request.user), pk=kwargs["pk"])
        cycles = cycles_for_user(self.request.user).filter(client=client).order_by("-created_at")
        retraits = client.retraits.order_by("-created_at")
        mouvements = client.mouvements.order_by("-created_at")

        context["client_profile"] = client
        context["cycles"] = cycles[:10]
        context["cycles_count"] = cycles.count()
        context["montant_total_retirable"] = get_montant_retirable(client)
        context["retraits"] = retraits[:10]
        context["mouvements"] = mouvements[:10]
        context["retrait_form"] = RetraitForm()
        context["can_withdraw"] = require_staff_role(self.request.user) and can_manage_client(self.request.user, client)
        return context


class ClientRetraitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        client = get_object_or_404(clients_for_user(request.user), pk=pk)

        if not require_staff_role(request.user) or not can_manage_client(request.user, client):
            return HttpResponseForbidden("Acces refuse.")

        form = RetraitForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Montant de retrait invalide.")
            return redirect("client-detail", pk=client.pk)

        try:
            create_retrait(client=client, montant=form.cleaned_data["montant"])
            messages.success(request, "Retrait enregistre avec succes.")
        except Exception as exc:
            messages.error(request, str(exc))

        return redirect("client-detail", pk=client.pk)


class AgentListView(LoginRequiredMixin, View):
    template_name = "agents/list.html"

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
            return HttpResponseForbidden("Acces refuse.")

        form = AgentForm(request.POST)
        if form.is_valid():
            agent = form.save()
            messages.success(request, "Agent cree avec succes.")
            return redirect("agent-detail", pk=agent.pk)

        return render(request, self.template_name, self.build_context(request, form), status=400)


class AgentDetailView(LoginRequiredMixin, TemplateView):
    template_name = "agents/detail.html"

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
        return context


class CycleListView(LoginRequiredMixin, View):
    template_name = "cycles/list.html"

    def build_context(self, request, form):
        queryset, filters = apply_cycle_filters(request, cycles_for_user(request.user), request.user)
        pagination = paginate_queryset(request, queryset)
        return {
            "cycles": pagination["object_list"],
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
            return HttpResponseForbidden("Acces refuse.")

        form = CycleForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                cycle = create_cycle(client=form.cleaned_data["client"], mise=form.cleaned_data["mise"])
                messages.success(request, "Cycle cree avec succes.")
                return redirect("cycle-detail", pk=cycle.pk)
            except Exception as exc:
                form.add_error(None, exc)

        return render(request, self.template_name, self.build_context(request, form), status=400)


class CycleDetailView(LoginRequiredMixin, TemplateView):
    template_name = "cycles/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = get_object_or_404(cycles_for_user(self.request.user), pk=kwargs["pk"])
        context["cycle"] = cycle
        context["depot_form"] = DepotForm(initial={"nb_mises": 1})
        context["depots"] = cycle.collectes.order_by("-created_at")
        context["mouvements"] = cycle.mouvements.order_by("-created_at")
        context["retenue"] = getattr(cycle, "retenue", None)
        context["can_operate"] = require_staff_role(self.request.user)
        context["montant_total_collecte"] = cycle.mise * cycle.nb_collectes
        context["montant_total_retirable"] = get_montant_retirable(cycle.client)
        return context


class CycleDepotView(LoginRequiredMixin, View):
    def post(self, request, pk):
        cycle = get_object_or_404(cycles_for_user(request.user), pk=pk)

        if not require_staff_role(request.user):
            return HttpResponseForbidden("Acces refuse.")

        if request.user.role == "AGENT":
            agent = agent_for_user(request.user)
            if agent is None or cycle.agent_id != agent.id:
                return HttpResponseForbidden("Ce cycle n'appartient pas a cet agent.")

        form = DepotForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Nombre de mises invalide.")
            return redirect("cycle-detail", pk=cycle.pk)

        try:
            create_depot(cycle=cycle, nb_mises=form.cleaned_data["nb_mises"])
            messages.success(request, "Depot enregistre avec succes.")
        except Exception as exc:
            messages.error(request, str(exc))

        return redirect("cycle-detail", pk=cycle.pk)


class MouvementListView(LoginRequiredMixin, View):
    template_name = "mouvements/list.html"

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
