import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_require_client_agent"),
        ("finance", "0007_add_sql_checks"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandeRetrait",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("type_demande", models.CharField(choices=[("ANTICIPE", "ANTICIPE"), ("NORMAL", "NORMAL")], max_length=20)),
                (
                    "statut",
                    models.CharField(
                        choices=[("EN_ATTENTE", "EN_ATTENTE"), ("VALIDEE", "VALIDEE"), ("REJETEE", "REJETEE")],
                        default="EN_ATTENTE",
                        max_length=20,
                    ),
                ),
                ("montant_souhaite", models.PositiveBigIntegerField(blank=True, null=True)),
                ("motif", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="demandes_retrait",
                        to="accounts.client",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="demandes_retrait_creees",
                        to="accounts.user",
                    ),
                ),
                (
                    "cycle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="demandes_retrait",
                        to="finance.cycle",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="demanderetrait",
            constraint=models.CheckConstraint(
                condition=models.Q(montant_souhaite__isnull=True) | models.Q(montant_souhaite__gt=0),
                name="demande_retrait_montant_positif_chk",
            ),
        ),
        migrations.AddConstraint(
            model_name="demanderetrait",
            constraint=models.CheckConstraint(
                condition=models.Q(type_demande__in=["ANTICIPE", "NORMAL"]),
                name="demande_retrait_type_chk",
            ),
        ),
        migrations.AddConstraint(
            model_name="demanderetrait",
            constraint=models.CheckConstraint(
                condition=models.Q(statut__in=["EN_ATTENTE", "VALIDEE", "REJETEE"]),
                name="demande_retrait_statut_chk",
            ),
        ),
    ]
