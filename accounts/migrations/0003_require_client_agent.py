from django.db import migrations, models
import django.db.models.deletion


def populate_client_agent(apps, schema_editor):
    Agent = apps.get_model("accounts", "Agent")
    Client = apps.get_model("accounts", "Client")

    default_agent = Agent.objects.order_by("id").first()

    for client in Client.objects.filter(agent__isnull=True):
        cycle = client.cycles.order_by("id").first()
        if cycle is not None:
            client.agent_id = cycle.agent_id
        elif default_agent is not None:
            client.agent_id = default_agent.id
        else:
            raise RuntimeError("Impossible de rattacher un client a un agent pendant la migration.")
        client.save(update_fields=["agent"])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("accounts", "0002_add_exam_fields"),
        ("finance", "0005_align_exam_domain"),
    ]

    operations = [
        migrations.RunPython(populate_client_agent, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="client",
            name="agent",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clients",
                to="accounts.agent",
            ),
        ),
    ]
