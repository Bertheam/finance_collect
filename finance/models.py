from django.core.exceptions import ValidationError
from django.db import models

from accounts.models import Agent, Client, User


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
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_cycles",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.mise and self.mise % 100 != 0:
            raise ValidationError({"mise": "La mise doit être un multiple de 100 FCFA."})
        if self.nb_collectes < 0 or self.nb_collectes > 31:
            raise ValidationError({"nb_collectes": "Le nombre de collectes doit rester entre 0 et 31."})
        if self.client_id and self.agent_id and self.client.agent_id != self.agent_id:
            raise ValidationError({"agent": "Le cycle doit être rattaché à l’agent du client."})

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
                raise ValidationError({"montant": "Le montant du dépôt doit être égal à mise * nb_mises."})

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
            raise ValidationError("La retenue doit être égale à la somme des commissions.")

    def __str__(self):
        return self.code


class Retrait(models.Model):
    code = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="retraits")
    montant = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class DemandeRetrait(models.Model):
    TYPE_CHOICES = (
        ("ANTICIPE", "ANTICIPE"),
        ("NORMAL", "NORMAL"),
    )

    STATUT_CHOICES = (
        ("EN_ATTENTE", "EN_ATTENTE"),
        ("VALIDEE", "VALIDEE"),
        ("REJETEE", "REJETEE"),
    )

    code = models.CharField(max_length=50, unique=True)
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name="demandes_retrait")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="demandes_retrait")
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandes_retrait_creees",
    )
    processed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandes_retrait_traitees",
    )
    type_demande = models.CharField(max_length=20, choices=TYPE_CHOICES)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="EN_ATTENTE")
    montant_souhaite = models.PositiveBigIntegerField(null=True, blank=True)
    motif = models.TextField(blank=True)
    commentaire_traitement = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    retrait = models.OneToOneField(
        "finance.Retrait",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demande_source",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.client_id and self.cycle_id and self.client_id != self.cycle.client_id:
            raise ValidationError({"client": "La demande doit être rattachée au client du cycle."})
        if self.montant_souhaite is not None and self.montant_souhaite <= 0:
            raise ValidationError({"montant_souhaite": "Le montant souhaité doit être positif."})

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant_souhaite__isnull=True) | models.Q(montant_souhaite__gt=0),
                name="demande_retrait_montant_positif_chk",
            ),
            models.CheckConstraint(
                condition=models.Q(type_demande__in=["ANTICIPE", "NORMAL"]),
                name="demande_retrait_type_chk",
            ),
            models.CheckConstraint(
                condition=models.Q(statut__in=["EN_ATTENTE", "VALIDEE", "REJETEE"]),
                name="demande_retrait_statut_chk",
            ),
        ]

    def __str__(self):
        return self.code
