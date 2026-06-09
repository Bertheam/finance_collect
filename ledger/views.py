from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import MouvementFinancier
from .serializers import MouvementFinancierSerializer


class MouvementFinancierViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = MouvementFinancierSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = MouvementFinancier.objects.select_related("cycle", "client", "agent").order_by("-created_at")

        cycle_id = self.request.query_params.get("cycle_id")
        client_id = self.request.query_params.get("client_id")
        mouvement_type = self.request.query_params.get("type_mouvement")

        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)

        if client_id:
            queryset = queryset.filter(client_id=client_id)

        if mouvement_type:
            queryset = queryset.filter(type_mouvement=mouvement_type)

        if user.role == "ADMIN":
            return queryset

        if user.role == "AGENT":
            agent = getattr(user, "agent_profile", None)
            if agent is None:
                return queryset.none()
            return queryset.filter(agent=agent)

        if user.role == "CLIENT":
            client = getattr(user, "client_profile", None)
            if client is None:
                return queryset.none()
            return queryset.filter(client=client)

        return queryset.none()
