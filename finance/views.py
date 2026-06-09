from django.core.exceptions import ValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminOrAgent

from .models import Collecte, Cycle, Retrait
from .serializers import (
    CycleCreateSerializer,
    CycleDetailSerializer,
    CycleSerializer,
    DepotCreateSerializer,
    DepotSerializer,
    RetraitCreateSerializer,
    RetraitSerializer,
)
from .services import create_cycle, create_depot, create_retrait


class CycleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Cycle.objects.select_related(
                "client",
                "client__agent",
                "client__user",
                "agent",
                "agent__user",
            )
            .prefetch_related("collectes", "mouvements")
            .order_by("-created_at")
        )

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

    def get_serializer_class(self):
        if self.action == "create":
            return CycleCreateSerializer
        if self.action == "retrieve":
            return CycleDetailSerializer
        return CycleSerializer

    def get_permissions(self):
        if self.action in {"create", "depot"}:
            return [IsAuthenticated(), IsAdminOrAgent()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client = serializer.validated_data["client"]
        user = request.user

        if user.role == "AGENT":
            own_agent = getattr(user, "agent_profile", None)
            if own_agent is None or client.agent_id != own_agent.id:
                return Response(
                    {"detail": "Un agent ne peut ouvrir un cycle que pour ses propres clients."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            cycle = create_cycle(client=client, mise=serializer.validated_data["mise"])
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        output = CycleSerializer(cycle, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="depot")
    def depot(self, request, pk=None):
        cycle = self.get_object()
        serializer = DepotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if request.user.role == "AGENT":
            own_agent = getattr(request.user, "agent_profile", None)
            if own_agent is None or cycle.agent_id != own_agent.id:
                return Response(
                    {"detail": "Ce cycle n'appartient pas a cet agent."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            create_depot(cycle=cycle, nb_mises=serializer.validated_data["nb_mises"])
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        cycle.refresh_from_db()
        return Response(CycleDetailSerializer(cycle, context=self.get_serializer_context()).data)


class DepotViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = DepotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Collecte.objects.select_related("cycle", "cycle__client", "cycle__agent").order_by("-created_at")
        cycle_id = self.request.query_params.get("cycle_id")

        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)

        if user.role == "ADMIN":
            return queryset

        if user.role == "AGENT":
            agent = getattr(user, "agent_profile", None)
            if agent is None:
                return queryset.none()
            return queryset.filter(cycle__agent=agent)

        if user.role == "CLIENT":
            client = getattr(user, "client_profile", None)
            if client is None:
                return queryset.none()
            return queryset.filter(cycle__client=client)

        return queryset.none()


class RetraitViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Retrait.objects.select_related("client", "client__agent", "client__user").order_by("-created_at")
        client_id = self.request.query_params.get("client_id")

        if client_id:
            queryset = queryset.filter(client_id=client_id)

        if user.role == "ADMIN":
            return queryset

        if user.role == "AGENT":
            agent = getattr(user, "agent_profile", None)
            if agent is None:
                return queryset.none()
            return queryset.filter(client__agent=agent)

        if user.role == "CLIENT":
            client = getattr(user, "client_profile", None)
            if client is None:
                return queryset.none()
            return queryset.filter(client=client)

        return queryset.none()

    def get_serializer_class(self):
        if self.action == "create":
            return RetraitCreateSerializer
        return RetraitSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsAdminOrAgent()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client = serializer.validated_data["client"]
        user = request.user

        if user.role == "AGENT":
            own_agent = getattr(user, "agent_profile", None)
            if own_agent is None or client.agent_id != own_agent.id:
                return Response(
                    {"detail": "Un agent ne peut effectuer un retrait que pour ses propres clients."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            retrait = create_retrait(client=client, montant=serializer.validated_data["montant"])
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        output = RetraitSerializer(retrait, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)
