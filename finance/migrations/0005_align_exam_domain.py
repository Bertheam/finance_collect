from django.db import migrations, models
import django.db.models.deletion


def populate_finance_domain(apps, schema_editor):
    Client = apps.get_model("accounts", "Client")
    Cycle = apps.get_model("finance", "Cycle")
    Collecte = apps.get_model("finance", "Collecte")

    for cycle in Cycle.objects.all():
        cycle.mise = int(cycle.mise or 0)
        cycle.solde_actuel = int(cycle.solde_actuel or 0)
        if cycle.type_cloture not in (None, "", "AUTOMATIQUE"):
            cycle.type_cloture = None
        cycle.save(update_fields=["mise", "solde_actuel", "type_cloture"])

    for client in Client.objects.filter(agent__isnull=True):
        cycle = Cycle.objects.filter(client_id=client.id).order_by("id").first()
        if cycle is not None:
            client.agent_id = cycle.agent_id
            client.save(update_fields=["agent"])

    for collecte in Collecte.objects.select_related("cycle"):
        cycle_mise = int(collecte.cycle.mise or 0)
        montant = int(collecte.montant or 0)
        nb_mises = 1
        if cycle_mise > 0:
            quotient = montant // cycle_mise
            nb_mises = quotient if quotient > 0 else 1

        collecte.code = f"DEP-LEGACY-{collecte.id}"
        collecte.nb_mises = nb_mises
        collecte.montant = montant
        collecte.save(update_fields=["code", "nb_mises", "montant"])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("accounts", "0002_add_exam_fields"),
        ("finance", "0004_use_bigint_for_finance_routines"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cycle",
            name="mise",
            field=models.PositiveBigIntegerField(),
        ),
        migrations.AlterField(
            model_name="cycle",
            name="solde_actuel",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="cycle",
            name="type_cloture",
            field=models.CharField(blank=True, choices=[("AUTOMATIQUE", "AUTOMATIQUE")], max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="collecte",
            name="code",
            field=models.CharField(max_length=50, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="collecte",
            name="nb_mises",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="collecte",
            name="montant",
            field=models.PositiveBigIntegerField(),
        ),
        migrations.CreateModel(
            name="Retenue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("montant", models.PositiveBigIntegerField()),
                ("commission_agent", models.PositiveBigIntegerField()),
                ("commission_institution", models.PositiveBigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("cycle", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="retenue", to="finance.cycle")),
            ],
        ),
        migrations.CreateModel(
            name="Retrait",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("montant", models.PositiveBigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="retraits", to="accounts.client")),
            ],
        ),
        migrations.RunPython(populate_finance_domain, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="collecte",
            name="code",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AlterField(
            model_name="collecte",
            name="nb_mises",
            field=models.PositiveIntegerField(),
        ),
    ]
