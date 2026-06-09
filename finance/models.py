from django.core.exceptions import ValidationError
from django.db import models

from accounts.models import Agent, Client


class Cycle(models.Model):
    STATUS_CHOICES = (
        ("EN_COURS", "EN_COURS"),
        ("CLOTURE", "CLOTURE"),
    )

    TYPE_CLOTURE = (
        ("AUTOMATIQUE", "AUTOMATIQUE"),
    )

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="cycles")
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="cycles")
    mise = models.PositiveBigIntegerField()
    nb_collectes = models.IntegerField(default=0)
    solde_actuel = models.PositiveBigIntegerField(default=0)
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default="EN_COURS")
    type_cloture = models.CharField(max_length=20, choices=TYPE_CLOTURE, null=True, blank=True)
    date_cloture = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.mise and self.mise % 100 != 0:
            raise ValidationError({"mise": "La mise doit etre un multiple de 100 FCFA."})
        if self.nb_collectes < 0 or self.nb_collectes > 31:
            raise ValidationError({"nb_collectes": "Le nombre de collectes doit rester entre 0 et 31."})
        if self.client_id and self.agent_id and self.client.agent_id != self.agent_id:
            raise ValidationError({"agent": "Le cycle doit etre rattache a l'agent du client."})

    def __str__(self):
        return f"Cycle #{self.id}"


class Collecte(models.Model):
    code = models.CharField(max_length=50, unique=True)
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name="collectes")
    nb_mises = models.PositiveIntegerField()
    montant = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.cycle_id and self.nb_mises and self.montant:
            expected = self.cycle.mise * self.nb_mises
            if self.montant != expected:
                raise ValidationError({"montant": "Le montant du depot doit etre egal a mise * nb_mises."})

    def __str__(self):
        return self.code


class Retenue(models.Model):
    code = models.CharField(max_length=50, unique=True)
    cycle = models.OneToOneField(Cycle, on_delete=models.PROTECT, related_name="retenue")
    montant = models.PositiveBigIntegerField()
    commission_agent = models.PositiveBigIntegerField()
    commission_institution = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.montant != self.commission_agent + self.commission_institution:
            raise ValidationError("La retenue doit etre egale a la somme des commissions.")

    def __str__(self):
        return self.code


class Retrait(models.Model):
    code = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="retraits")
    montant = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code
