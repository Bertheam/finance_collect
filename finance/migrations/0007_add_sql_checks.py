from django.db import migrations


ADD_SQL_CHECKS = """
ALTER TABLE finance.finance_cycle
DROP CONSTRAINT IF EXISTS cycle_mise_positive_chk,
DROP CONSTRAINT IF EXISTS cycle_mise_multiple_100_chk,
DROP CONSTRAINT IF EXISTS cycle_nb_collectes_range_chk,
DROP CONSTRAINT IF EXISTS cycle_solde_non_negatif_chk,
DROP CONSTRAINT IF EXISTS cycle_statut_cloture_chk;

ALTER TABLE finance.finance_cycle
ADD CONSTRAINT cycle_mise_positive_chk CHECK (mise > 0),
ADD CONSTRAINT cycle_mise_multiple_100_chk CHECK (mod(mise, 100) = 0),
ADD CONSTRAINT cycle_nb_collectes_range_chk CHECK (nb_collectes BETWEEN 0 AND 31),
ADD CONSTRAINT cycle_solde_non_negatif_chk CHECK (solde_actuel >= 0),
ADD CONSTRAINT cycle_statut_cloture_chk CHECK (
    (
        statut = 'EN_COURS'
        AND type_cloture IS NULL
        AND date_cloture IS NULL
    )
    OR
    (
        statut = 'CLOTURE'
        AND type_cloture = 'AUTOMATIQUE'
        AND date_cloture IS NOT NULL
    )
);

ALTER TABLE finance.finance_collecte
DROP CONSTRAINT IF EXISTS collecte_nb_mises_positive_chk,
DROP CONSTRAINT IF EXISTS collecte_montant_positive_chk;

ALTER TABLE finance.finance_collecte
ADD CONSTRAINT collecte_nb_mises_positive_chk CHECK (nb_mises > 0),
ADD CONSTRAINT collecte_montant_positive_chk CHECK (montant > 0);

ALTER TABLE finance.finance_retenue
DROP CONSTRAINT IF EXISTS retenue_montant_positive_chk,
DROP CONSTRAINT IF EXISTS retenue_commissions_non_negatives_chk,
DROP CONSTRAINT IF EXISTS retenue_total_coherent_chk;

ALTER TABLE finance.finance_retenue
ADD CONSTRAINT retenue_montant_positive_chk CHECK (montant > 0),
ADD CONSTRAINT retenue_commissions_non_negatives_chk CHECK (
    commission_agent >= 0
    AND commission_institution >= 0
),
ADD CONSTRAINT retenue_total_coherent_chk CHECK (
    commission_agent + commission_institution = montant
);

ALTER TABLE finance.finance_retrait
DROP CONSTRAINT IF EXISTS retrait_montant_positive_chk;

ALTER TABLE finance.finance_retrait
ADD CONSTRAINT retrait_montant_positive_chk CHECK (montant > 0);

ALTER TABLE finance.ledger_mouvementfinancier
DROP CONSTRAINT IF EXISTS mouvement_montant_positive_chk,
DROP CONSTRAINT IF EXISTS mouvement_rattachement_chk,
DROP CONSTRAINT IF EXISTS mouvement_flux_chk;

ALTER TABLE finance.ledger_mouvementfinancier
ADD CONSTRAINT mouvement_montant_positive_chk CHECK (montant > 0),
ADD CONSTRAINT mouvement_rattachement_chk CHECK (
    (
        type_mouvement = 'RETRAIT'
        AND cycle_id IS NULL
        AND client_id IS NOT NULL
        AND agent_id IS NOT NULL
    )
    OR
    (
        type_mouvement IN ('MISE', 'RETENUE', 'COM_AGENT', 'COM_INSTITUTION', 'CREDIT_CLIENT')
        AND cycle_id IS NOT NULL
        AND client_id IS NOT NULL
        AND agent_id IS NOT NULL
    )
),
ADD CONSTRAINT mouvement_flux_chk CHECK (
    (type_mouvement = 'MISE' AND source = 'CLIENT' AND destination = 'CYCLE')
    OR
    (type_mouvement = 'RETENUE' AND source = 'CYCLE' AND destination = 'INSTITUTION')
    OR
    (type_mouvement = 'COM_AGENT' AND source = 'INSTITUTION' AND destination = 'AGENT')
    OR
    (type_mouvement = 'COM_INSTITUTION' AND source = 'INSTITUTION' AND destination = 'INSTITUTION')
    OR
    (type_mouvement = 'CREDIT_CLIENT' AND source = 'CYCLE' AND destination = 'CLIENT')
    OR
    (type_mouvement = 'RETRAIT' AND source = 'INSTITUTION' AND destination = 'CLIENT')
);
"""


DROP_SQL_CHECKS = """
ALTER TABLE finance.ledger_mouvementfinancier
DROP CONSTRAINT IF EXISTS mouvement_flux_chk,
DROP CONSTRAINT IF EXISTS mouvement_rattachement_chk,
DROP CONSTRAINT IF EXISTS mouvement_montant_positive_chk;

ALTER TABLE finance.finance_retrait
DROP CONSTRAINT IF EXISTS retrait_montant_positive_chk;

ALTER TABLE finance.finance_retenue
DROP CONSTRAINT IF EXISTS retenue_total_coherent_chk,
DROP CONSTRAINT IF EXISTS retenue_commissions_non_negatives_chk,
DROP CONSTRAINT IF EXISTS retenue_montant_positive_chk;

ALTER TABLE finance.finance_collecte
DROP CONSTRAINT IF EXISTS collecte_montant_positive_chk,
DROP CONSTRAINT IF EXISTS collecte_nb_mises_positive_chk;

ALTER TABLE finance.finance_cycle
DROP CONSTRAINT IF EXISTS cycle_statut_cloture_chk,
DROP CONSTRAINT IF EXISTS cycle_solde_non_negatif_chk,
DROP CONSTRAINT IF EXISTS cycle_nb_collectes_range_chk,
DROP CONSTRAINT IF EXISTS cycle_mise_multiple_100_chk,
DROP CONSTRAINT IF EXISTS cycle_mise_positive_chk;
"""


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("finance", "0006_refresh_finance_sql"),
    ]

    operations = [
        migrations.RunSQL(
            sql=ADD_SQL_CHECKS,
            reverse_sql=DROP_SQL_CHECKS,
        ),
    ]
