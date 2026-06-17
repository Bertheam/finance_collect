from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    ROLE_CHOICES = (
        ('ADMIN', 'ADMIN'),
        ('CLIENT', 'CLIENT'),
        ('AGENT', 'AGENT'),
    )

    telephone = models.CharField(
        max_length=30,
        unique=True
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    mfa_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class Notification(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    title = models.CharField(max_length=140)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.user.username}"


class Agent(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_profile'
    )

    matricule = models.CharField(
        max_length=50,
        unique=True
    )

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)

    telephone = models.CharField(max_length=30)

    zone = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    commission_totale = models.PositiveBigIntegerField(
        default=0
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_agents'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.matricule})"


class Client(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_profile'
    )

    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name='clients'
    )

    code_client = models.CharField(
        max_length=50,
        unique=True
    )

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)

    telephone = models.CharField(max_length=30)

    email = models.EmailField(
        null=True,
        blank=True
    )

    adresse = models.TextField(
        null=True,
        blank=True
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_clients'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.code_client})"
