from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .services import create_agent, create_client
from .models import Agent, Client, User


TEXT_INPUT_CLASSES = (
    "mt-2 w-full rounded-2xl border border-stone-300 bg-white/90 px-4 py-3 "
    "text-sm text-stone-900 shadow-sm outline-none transition "
    "focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
)
CHECKBOX_CLASSES = "h-4 w-4 rounded border-stone-300 text-amber-600 focus:ring-amber-500"


class TailwindFormMixin:
    def apply_tailwind(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = CHECKBOX_CLASSES
                continue

            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {TEXT_INPUT_CLASSES}".strip()


class MonolithAuthenticationForm(TailwindFormMixin, AuthenticationForm):
    username = forms.CharField(label="Nom d'utilisateur")
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class AccountBackedProfileForm(TailwindFormMixin, forms.ModelForm):
    create_account = forms.BooleanField(
        label="Creer un compte utilisateur",
        required=False,
    )
    username = forms.CharField(label="Nom d'utilisateur", required=False)
    password = forms.CharField(label="Mot de passe", required=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(
        label="Confirmer le mot de passe",
        required=False,
        widget=forms.PasswordInput,
    )
    first_name = forms.CharField(label="Prenom", required=False)
    last_name = forms.CharField(label="Nom", required=False)
    email = forms.EmailField(label="Email", required=False)

    account_role = None
    account_checkbox_label = "Creer un compte utilisateur"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["create_account"].label = self.account_checkbox_label
        self.apply_tailwind()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("create_account"):
            return cleaned_data

        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        telephone = cleaned_data.get("telephone")
        email = cleaned_data.get("email")

        if not username:
            self.add_error("username", "Le nom d'utilisateur est requis.")
        elif User.objects.filter(username=username).exists():
            self.add_error("username", "Ce nom d'utilisateur existe deja.")

        if not password:
            self.add_error("password", "Le mot de passe est requis.")

        if not password_confirm:
            self.add_error("password_confirm", "La confirmation du mot de passe est requise.")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Les mots de passe ne correspondent pas.")

        if password:
            temp_user = User(
                username=username or "",
                telephone=telephone or "",
                role=self.account_role or "",
                email=email or "",
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password, user=temp_user)
            except ValidationError as exc:
                self.add_error("password", exc)

        if telephone and User.objects.filter(telephone=telephone).exists():
            self.add_error("telephone", "Ce telephone est deja utilise par un compte.")

        if email and User.objects.filter(email=email).exclude(email="").exists():
            self.add_error("email", "Cet email est deja utilise.")

        return cleaned_data

    def build_user(self):
        return {
            "username": self.cleaned_data["username"],
            "password": self.cleaned_data["password"],
            "telephone": self.cleaned_data["telephone"],
            "first_name": self.cleaned_data.get("first_name", ""),
            "last_name": self.cleaned_data.get("last_name", ""),
            "email": self.cleaned_data.get("email", ""),
        }

    def save(self, commit=True):
        raise NotImplementedError


class ClientForm(AccountBackedProfileForm):
    account_role = "CLIENT"
    account_checkbox_label = "Creer un compte client"

    class Meta:
        model = Client
        fields = [
            "agent",
            "code_client",
            "nom",
            "prenom",
            "telephone",
            "email",
            "adresse",
        ]
        labels = {
            "agent": "Agent responsable",
            "code_client": "Code client",
            "nom": "Nom",
            "prenom": "Prenom",
            "telephone": "Telephone",
            "email": "Email",
            "adresse": "Adresse",
        }
        widgets = {
            "adresse": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and getattr(user, "role", None) == "AGENT":
            agent = getattr(user, "agent_profile", None)
            if agent is not None:
                self.fields["agent"].queryset = Agent.objects.filter(pk=agent.pk)
                self.fields["agent"].initial = agent

    def save(self, commit=True):
        payload = {
            "agent": self.cleaned_data["agent"],
            "code_client": self.cleaned_data["code_client"],
            "nom": self.cleaned_data["nom"],
            "prenom": self.cleaned_data["prenom"],
            "telephone": self.cleaned_data["telephone"],
            "email": self.cleaned_data.get("email", ""),
            "adresse": self.cleaned_data.get("adresse", ""),
            "create_account": self.cleaned_data.get("create_account", False),
        }
        if self.cleaned_data.get("create_account"):
            payload.update(self.build_user())
        return create_client(**payload)


class AgentForm(AccountBackedProfileForm):
    account_role = "AGENT"
    account_checkbox_label = "Creer un compte agent"

    class Meta:
        model = Agent
        fields = [
            "matricule",
            "nom",
            "prenom",
            "telephone",
            "zone",
        ]
        labels = {
            "matricule": "Matricule",
            "nom": "Nom",
            "prenom": "Prenom",
            "telephone": "Telephone",
            "zone": "Zone",
        }

    def save(self, commit=True):
        payload = {
            "matricule": self.cleaned_data["matricule"],
            "nom": self.cleaned_data["nom"],
            "prenom": self.cleaned_data["prenom"],
            "telephone": self.cleaned_data["telephone"],
            "zone": self.cleaned_data.get("zone", ""),
            "create_account": self.cleaned_data.get("create_account", False),
        }
        if self.cleaned_data.get("create_account"):
            payload.update(self.build_user())
        return create_agent(**payload)
