from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

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
    username = forms.CharField(
        label="Nom d’utilisateur",
        error_messages={"required": "Le nom d’utilisateur est requis."},
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput,
        error_messages={"required": "Le mot de passe est requis."},
    )
    error_messages = {
        "invalid_login": _(
            "Veuillez saisir un nom d'utilisateur et un mot de passe valides. "
            "Les deux champs peuvent être sensibles à la casse."
        ),
        "inactive": _("Ce compte est inactif."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind()


class AccountBackedProfileForm(TailwindFormMixin, forms.ModelForm):
    create_account = forms.BooleanField(
        label="Créer un compte utilisateur",
        required=False,
    )
    username = forms.CharField(label="Nom d’utilisateur", required=False)
    password = forms.CharField(label="Mot de passe", required=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(
        label="Confirmer le mot de passe",
        required=False,
        widget=forms.PasswordInput,
    )

    account_role = None
    account_checkbox_label = "Créer un compte utilisateur"
    account_required = False
    show_account_toggle = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.show_account_toggle:
            self.fields["create_account"].label = self.account_checkbox_label
        else:
            self.fields.pop("create_account", None)
        self.apply_tailwind()

    def clean(self):
        cleaned_data = super().clean()
        account_enabled = self.account_required or cleaned_data.get("create_account")
        cleaned_data["create_account"] = account_enabled

        if not account_enabled:
            return cleaned_data

        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        telephone = cleaned_data.get("telephone")

        if not username:
            self.add_error("username", "Le nom d’utilisateur est requis.")
        elif User.objects.filter(username=username).exists():
            self.add_error("username", "Ce nom d’utilisateur existe déjà.")

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
            )
            try:
                validate_password(password, user=temp_user)
            except ValidationError as exc:
                self.add_error("password", exc)

        if telephone and User.objects.filter(telephone=telephone).exists():
            self.add_error("telephone", "Ce téléphone est déjà utilisé par un autre compte.")

        return cleaned_data

    def build_user(self, *, first_name="", last_name="", email=""):
        return {
            "username": self.cleaned_data["username"],
            "password": self.cleaned_data["password"],
            "telephone": self.cleaned_data["telephone"],
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
        }

    def save(self, commit=True):
        raise NotImplementedError


class ClientForm(AccountBackedProfileForm):
    account_role = "CLIENT"
    account_checkbox_label = "Créer un compte client"

    class Meta:
        model = Client
        fields = [
            "agent",
            "nom",
            "prenom",
            "telephone",
            "email",
            "adresse",
        ]
        labels = {
            "agent": "Agent responsable",
            "nom": "Nom",
            "prenom": "Prénom",
            "telephone": "Téléphone",
            "email": "E-mail",
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
                self.fields["agent"].queryset = Agent.objects.filter(pk=agent.pk, deleted_at__isnull=True)
                self.fields["agent"].initial = agent
        else:
            self.fields["agent"].queryset = Agent.objects.filter(deleted_at__isnull=True).order_by("matricule")
        self.order_fields(
            [
                "agent",
                "nom",
                "prenom",
                "telephone",
                "email",
                "adresse",
                "create_account",
                "username",
                "password",
                "password_confirm",
            ]
        )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("create_account"):
            email = cleaned_data.get("email")
            if email and User.objects.filter(email=email).exclude(email="").exists():
                self.add_error("email", "Cet e-mail est déjà utilisé.")
        return cleaned_data

    def save(self, commit=True):
        payload = {
            "agent": self.cleaned_data["agent"],
            "nom": self.cleaned_data["nom"],
            "prenom": self.cleaned_data["prenom"],
            "telephone": self.cleaned_data["telephone"],
            "email": self.cleaned_data.get("email", ""),
            "adresse": self.cleaned_data.get("adresse", ""),
            "create_account": self.cleaned_data.get("create_account", False),
        }
        if self.cleaned_data.get("create_account"):
            payload.update(
                self.build_user(
                    first_name=self.cleaned_data["prenom"],
                    last_name=self.cleaned_data["nom"],
                    email=self.cleaned_data.get("email", ""),
                )
            )
        return create_client(**payload)


class AgentForm(AccountBackedProfileForm):
    account_role = "AGENT"
    account_required = True
    show_account_toggle = False

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
            "prenom": "Prénom",
            "telephone": "Téléphone",
            "zone": "Zone",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                "matricule",
                "nom",
                "prenom",
                "telephone",
                "zone",
                "username",
                "password",
                "password_confirm",
            ]
        )

    def save(self, commit=True):
        payload = {
            "matricule": self.cleaned_data["matricule"],
            "nom": self.cleaned_data["nom"],
            "prenom": self.cleaned_data["prenom"],
            "telephone": self.cleaned_data["telephone"],
            "zone": self.cleaned_data.get("zone", ""),
            "create_account": True,
        }
        payload.update(
            self.build_user(
                first_name=self.cleaned_data["prenom"],
                last_name=self.cleaned_data["nom"],
            )
        )
        return create_agent(**payload)


class ProfileUpdateFormMixin(TailwindFormMixin, forms.ModelForm):
    sync_email = False
    password = forms.CharField(label="Nouveau mot de passe", required=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        required=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.can_reset_password = bool(
            actor
            and getattr(actor, "role", None) == "ADMIN"
            and getattr(self.instance, "user", None) is not None
        )
        if not self.can_reset_password:
            self.fields.pop("password", None)
            self.fields.pop("password_confirm", None)
        self.apply_tailwind()

    def validate_linked_user_fields(self):
        linked_user = getattr(self.instance, "user", None)
        if linked_user is None:
            return

        telephone = self.cleaned_data.get("telephone")
        if telephone and User.objects.filter(telephone=telephone).exclude(pk=linked_user.pk).exists():
            self.add_error("telephone", "Ce téléphone est déjà utilisé par un autre compte.")

        if not self.sync_email:
            return

        email = (self.cleaned_data.get("email") or "").strip()
        if email and User.objects.filter(email=email).exclude(pk=linked_user.pk).exclude(email="").exists():
            self.add_error("email", "Cet e-mail est déjà utilisé.")

    def validate_optional_password_change(self):
        if not self.can_reset_password:
            return

        password = self.cleaned_data.get("password")
        password_confirm = self.cleaned_data.get("password_confirm")

        if not password and not password_confirm:
            return

        if not password:
            self.add_error("password", "Le mot de passe est requis.")
            return

        if not password_confirm:
            self.add_error("password_confirm", "La confirmation du mot de passe est requise.")
            return

        if password != password_confirm:
            self.add_error("password_confirm", "Les mots de passe ne correspondent pas.")
            return

        linked_user = getattr(self.instance, "user", None)
        try:
            validate_password(password, user=linked_user)
        except ValidationError as exc:
            self.add_error("password", exc)

    def sync_linked_user(self, instance):
        linked_user = getattr(instance, "user", None)
        if linked_user is None:
            return

        linked_user.first_name = self.cleaned_data.get("prenom", "")
        linked_user.last_name = self.cleaned_data.get("nom", "")
        linked_user.telephone = self.cleaned_data.get("telephone", "")
        update_fields = ["first_name", "last_name", "telephone"]

        if self.sync_email:
            linked_user.email = self.cleaned_data.get("email", "") or ""
            update_fields.append("email")

        password = self.cleaned_data.get("password")
        if self.can_reset_password and password:
            linked_user.set_password(password)
            linked_user.save()
            return

        linked_user.save(update_fields=update_fields)


class ClientUpdateForm(ProfileUpdateFormMixin):
    sync_email = True

    class Meta:
        model = Client
        fields = [
            "agent",
            "nom",
            "prenom",
            "telephone",
            "email",
            "adresse",
        ]
        labels = {
            "agent": "Agent responsable",
            "nom": "Nom",
            "prenom": "Prénom",
            "telephone": "Téléphone",
            "email": "E-mail",
            "adresse": "Adresse",
        }
        widgets = {
            "adresse": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, actor=None, **kwargs):
        super().__init__(*args, actor=actor, **kwargs)
        if user and getattr(user, "role", None) == "AGENT":
            agent = getattr(user, "agent_profile", None)
            if agent is not None:
                self.fields["agent"].queryset = Agent.objects.filter(pk=agent.pk, deleted_at__isnull=True)
        else:
            self.fields["agent"].queryset = Agent.objects.filter(deleted_at__isnull=True).order_by("matricule")
        ordered_fields = [
            "agent",
            "nom",
            "prenom",
            "telephone",
            "email",
            "adresse",
        ]
        if self.can_reset_password:
            ordered_fields.extend(["password", "password_confirm"])
        self.order_fields(ordered_fields)

    def clean(self):
        cleaned_data = super().clean()
        self.validate_linked_user_fields()
        self.validate_optional_password_change()
        return cleaned_data

    def save(self, commit=True):
        client = super().save(commit=commit)
        self.sync_linked_user(client)
        return client


class AgentUpdateForm(ProfileUpdateFormMixin):
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
            "prenom": "Prénom",
            "telephone": "Téléphone",
            "zone": "Zone",
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, actor=actor, **kwargs)
        ordered_fields = [
            "matricule",
            "nom",
            "prenom",
            "telephone",
            "zone",
        ]
        if self.can_reset_password:
            ordered_fields.extend(["password", "password_confirm"])
        self.order_fields(ordered_fields)

    def clean(self):
        cleaned_data = super().clean()
        self.validate_linked_user_fields()
        self.validate_optional_password_change()
        return cleaned_data

    def save(self, commit=True):
        agent = super().save(commit=commit)
        self.sync_linked_user(agent)
        return agent
