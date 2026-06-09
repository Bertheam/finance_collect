from django.contrib import admin
from django.urls import path
from config.web_views import (
    AgentDetailView,
    AgentListView,
    ClientDetailView,
    ClientListView,
    ClientRetraitView,
    CycleDetailView,
    CycleDepotView,
    CycleListView,
    DashboardView,
    MonolithLoginView,
    MonolithLogoutView,
    MouvementListView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", MonolithLoginView.as_view(), name="login"),
    path("logout/", MonolithLogoutView.as_view(), name="logout"),
    path("clients/", ClientListView.as_view(), name="clients"),
    path("clients/<int:pk>/", ClientDetailView.as_view(), name="client-detail"),
    path("clients/<int:pk>/retraits/", ClientRetraitView.as_view(), name="client-retrait"),
    path("agents/", AgentListView.as_view(), name="agents"),
    path("agents/<int:pk>/", AgentDetailView.as_view(), name="agent-detail"),
    path("cycles/", CycleListView.as_view(), name="cycles"),
    path("cycles/<int:pk>/", CycleDetailView.as_view(), name="cycle-detail"),
    path("cycles/<int:pk>/depots/", CycleDepotView.as_view(), name="cycle-depot"),
    path("mouvements/", MouvementListView.as_view(), name="mouvements"),
    path("admin/", admin.site.urls),
]
