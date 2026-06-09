from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Agent, Client
from .serializers import AgentSerializer, ClientSerializer, UserSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ClientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Client.objects.select_related("user", "agent", "agent__user").order_by("-created_at")

        if user.role == "ADMIN":
            return queryset

        if user.role == "CLIENT":
            return queryset.filter(user=user)

        if user.role == "AGENT":
            agent = getattr(user, "agent_profile", None)
            if agent is None:
                return queryset.none()
            return queryset.filter(agent=agent)

        return queryset.none()


class AgentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AgentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Agent.objects.select_related("user").order_by("-created_at")

        if user.role == "ADMIN":
            return queryset

        if user.role == "AGENT":
            return queryset.filter(user=user)

        return queryset.none()
