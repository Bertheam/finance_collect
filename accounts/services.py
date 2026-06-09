from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Agent, Client, User


def _create_user_account(*, username, password, telephone, role, first_name="", last_name="", email=""):
    temp_user = User(
        username=username,
        telephone=telephone,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    validate_password(password, user=temp_user)

    return User.objects.create_user(
        username=username,
        password=password,
        telephone=telephone,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )


@transaction.atomic
def create_agent(
    *,
    matricule,
    nom,
    prenom,
    telephone,
    zone="",
    create_account=False,
    username="",
    password="",
    first_name="",
    last_name="",
    email="",
):
    agent = Agent(
        matricule=matricule,
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        zone=zone,
    )
    agent.full_clean()
    agent.save()

    if create_account:
        user = _create_user_account(
            username=username,
            password=password,
            telephone=telephone,
            role="AGENT",
            first_name=first_name or prenom,
            last_name=last_name or nom,
            email=email,
        )
        agent.user = user
        agent.save(update_fields=["user"])

    return agent


@transaction.atomic
def create_client(
    *,
    agent,
    code_client,
    nom,
    prenom,
    telephone,
    email="",
    adresse="",
    create_account=False,
    username="",
    password="",
    first_name="",
    last_name="",
):
    client = Client(
        agent=agent,
        code_client=code_client,
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        email=email,
        adresse=adresse,
    )
    client.full_clean()
    client.save()

    if create_account:
        user = _create_user_account(
            username=username,
            password=password,
            telephone=telephone,
            role="CLIENT",
            first_name=first_name or prenom,
            last_name=last_name or nom,
            email=email,
        )
        client.user = user
        client.save(update_fields=["user"])

    return client
