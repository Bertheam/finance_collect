from django.db import migrations, models
import django.db.models.deletion


LEGACY_TYPE_MAPPING = {
    "COLLECTE": "MISE",
    "MISE_RETENUE": "RETENUE",
    "PART_AGENT": "COM_AGENT",
    "PART_INSTITUTION": "COM_INSTITUTION",
    "RETRAIT_CLIENT": "CREDIT_CLIENT",
    "PENALITE": "RETENUE",
}


def populate_ledger_links(apps, schema_editor):
    MouvementFinancier = apps.get_model("ledger", "MouvementFinancier")

    for mouvement in MouvementFinancier.objects.select_related("cycle"):
        if mouvement.type_mouvement in LEGACY_TYPE_MAPPING:
            mouvement.type_mouvement = LEGACY_TYPE_MAPPING[mouvement.type_mouvement]

        if mouvement.cycle_id is not None:
            mouvement.client_id = mouvement.cycle.client_id
            mouvement.agent_id = mouvement.cycle.agent_id

        mouvement.montant = int(mouvement.montant or 0)
        mouvement.save(update_fields=["type_mouvement", "client", "agent", "montant"])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("accounts", "0003_require_client_agent"),
        ("finance", "0005_align_exam_domain"),
        ("ledger", "0002_remove_mouvementfinancier_agent_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="mouvementfinancier",
            name="agent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mouvements",
                to="accounts.agent",
            ),
        ),
        migrations.AddField(
            model_name="mouvementfinancier",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mouvements",
                to="accounts.client",
            ),
        ),
        migrations.AlterField(
            model_name="mouvementfinancier",
            name="cycle",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mouvements",
                to="finance.cycle",
            ),
        ),
        migrations.AlterField(
            model_name="mouvementfinancier",
            name="montant",
            field=models.PositiveBigIntegerField(),
        ),
        migrations.AlterField(
            model_name="mouvementfinancier",
            name="type_mouvement",
            field=models.CharField(
                choices=[
                    ("MISE", "MISE"),
                    ("RETENUE", "RETENUE"),
                    ("COM_AGENT", "COM_AGENT"),
                    ("COM_INSTITUTION", "COM_INSTITUTION"),
                    ("CREDIT_CLIENT", "CREDIT_CLIENT"),
                    ("RETRAIT", "RETRAIT"),
                ],
                max_length=50,
            ),
        ),
        migrations.RunPython(populate_ledger_links, migrations.RunPython.noop),
    ]
