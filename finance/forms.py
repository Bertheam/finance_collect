from django import forms

from accounts.forms import TailwindFormMixin
from accounts.models import Client

from .models import Cycle


class CycleForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Cycle
        fields = ["client", "mise"]
        labels = {
            "client": "Client",
            "mise": "Mise",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        queryset = Client.objects.select_related("agent").filter(
            deleted_at__isnull=True,
            agent__deleted_at__isnull=True,
        ).order_by("code_client")

        if user and user.role == "AGENT":
            agent = getattr(user, "agent_profile", None)
            if agent is not None:
                queryset = queryset.filter(agent=agent)

        self.fields["client"].queryset = queryset

        self.apply_tailwind()


class DepotForm(TailwindFormMixin, forms.Form):
    nb_mises = forms.IntegerField(
        label="Nombre de mises",
        min_value=1,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class RetraitForm(TailwindFormMixin, forms.Form):
    montant = forms.IntegerField(
        label="Montant du retrait",
        min_value=1,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class DemandeRetraitForm(TailwindFormMixin, forms.Form):
    TYPE_CHOICES = (
        ("ANTICIPE", "Retrait anticipé"),
        ("NORMAL", "Retrait normal"),
    )

    type_demande = forms.ChoiceField(
        label="Type de demande",
        choices=TYPE_CHOICES,
    )
    montant_souhaite = forms.IntegerField(
        label="Montant souhaité",
        min_value=1,
        required=False,
    )
    motif = forms.CharField(
        label="Motif",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()
