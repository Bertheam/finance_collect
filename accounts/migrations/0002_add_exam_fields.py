from django.db import migrations, models
import django.db.models.deletion


def populate_profile_names(apps, schema_editor):
    Agent = apps.get_model("accounts", "Agent")
    Client = apps.get_model("accounts", "Client")

    for agent in Agent.objects.select_related("user"):
        user = getattr(agent, "user", None)
        agent.nom = (getattr(user, "last_name", "") or "Agent").strip() or "Agent"
        agent.prenom = (getattr(user, "first_name", "") or agent.matricule).strip() or agent.matricule
        agent.commission_totale = int(agent.commission_totale or 0)
        agent.save(update_fields=["nom", "prenom", "commission_totale"])

    for client in Client.objects.select_related("user"):
        user = getattr(client, "user", None)
        client.nom = (getattr(user, "last_name", "") or "Client").strip() or "Client"
        client.prenom = (getattr(user, "first_name", "") or client.code_client).strip() or client.code_client
        email = (getattr(user, "email", "") or "").strip()
        client.email = email or None
        client.save(update_fields=["nom", "prenom", "email"])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="nom",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="agent",
            name="prenom",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="agent",
            name="commission_totale",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="client",
            name="agent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clients",
                to="accounts.agent",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="nom",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="prenom",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.RunPython(populate_profile_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="agent",
            name="nom",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="agent",
            name="prenom",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="client",
            name="nom",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="client",
            name="prenom",
            field=models.CharField(max_length=100),
        ),
    ]
