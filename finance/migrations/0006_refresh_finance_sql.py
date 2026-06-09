from django.db import migrations


REFRESH_FINANCE_SQL = """
DROP TRIGGER IF EXISTS trg_sync_solde_cycle
ON finance.ledger_mouvementfinancier;

DROP TRIGGER IF EXISTS trg_sync_commission_agent_on_cycle
ON finance.finance_cycle;

DROP TRIGGER IF EXISTS trg_sync_commission_agent_on_ledger
ON finance.ledger_mouvementfinancier;

DROP FUNCTION IF EXISTS finance.sync_solde_cycle();
DROP FUNCTION IF EXISTS finance.calcul_solde_reel(bigint);
DROP FUNCTION IF EXISTS finance.calcul_solde_reel(integer);
DROP FUNCTION IF EXISTS finance.peut_retirer(bigint);
DROP FUNCTION IF EXISTS finance.peut_retirer(integer);
DROP PROCEDURE IF EXISTS finance.cloture_normale(bigint);
DROP PROCEDURE IF EXISTS finance.cloture_normale(integer);
DROP PROCEDURE IF EXISTS finance.retrait_anticipe(bigint);
DROP PROCEDURE IF EXISTS finance.retrait_anticipe(integer);
DROP FUNCTION IF EXISTS finance.sync_commission_agent_from_cycle();
DROP FUNCTION IF EXISTS finance.sync_commission_agent_from_ledger();
DROP FUNCTION IF EXISTS finance.sync_commission_totale_for_agent(bigint);
DROP FUNCTION IF EXISTS finance.calcul_commission_agent(bigint);
DROP FUNCTION IF EXISTS finance.calcul_montant_retirable(bigint);
DROP PROCEDURE IF EXISTS finance.effectuer_collecte(bigint, numeric);
DROP PROCEDURE IF EXISTS finance.effectuer_collecte(integer, numeric);

CREATE OR REPLACE FUNCTION finance.calcul_commission_agent(p_agent_id bigint)
RETURNS bigint
LANGUAGE plpgsql
AS $function$
DECLARE
    v_total bigint := 0;
BEGIN
    SELECT COALESCE(SUM(m.montant), 0)::bigint
    INTO v_total
    FROM finance.ledger_mouvementfinancier AS m
    WHERE m.agent_id = p_agent_id
      AND m.type_mouvement = 'COM_AGENT';

    RETURN v_total;
END;
$function$;

CREATE OR REPLACE FUNCTION finance.calcul_montant_retirable(p_client_id bigint)
RETURNS bigint
LANGUAGE plpgsql
AS $function$
DECLARE
    v_total bigint := 0;
BEGIN
    SELECT COALESCE(
        SUM(
            CASE
                WHEN m.type_mouvement = 'CREDIT_CLIENT' THEN m.montant
                WHEN m.type_mouvement = 'RETRAIT' THEN -m.montant
                ELSE 0
            END
        ),
        0
    )::bigint
    INTO v_total
    FROM finance.ledger_mouvementfinancier AS m
    WHERE m.client_id = p_client_id;

    RETURN v_total;
END;
$function$;

CREATE OR REPLACE FUNCTION finance.sync_commission_totale_for_agent(p_agent_id bigint)
RETURNS void
LANGUAGE plpgsql
AS $function$
BEGIN
    IF p_agent_id IS NULL THEN
        RETURN;
    END IF;

    UPDATE finance.accounts_agent
    SET commission_totale = finance.calcul_commission_agent(p_agent_id)
    WHERE id = p_agent_id;
END;
$function$;

CREATE OR REPLACE FUNCTION finance.sync_commission_agent_from_ledger()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_old_agent_id bigint;
    v_new_agent_id bigint;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_old_agent_id := OLD.agent_id;
    END IF;

    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        v_new_agent_id := NEW.agent_id;
    END IF;

    PERFORM finance.sync_commission_totale_for_agent(v_old_agent_id);

    IF v_new_agent_id IS DISTINCT FROM v_old_agent_id THEN
        PERFORM finance.sync_commission_totale_for_agent(v_new_agent_id);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$function$;

CREATE TRIGGER trg_sync_commission_agent_on_ledger
AFTER INSERT OR UPDATE OR DELETE
ON finance.ledger_mouvementfinancier
FOR EACH ROW
EXECUTE FUNCTION finance.sync_commission_agent_from_ledger();

UPDATE finance.accounts_agent AS agent
SET commission_totale = finance.calcul_commission_agent(agent.id);
"""


DROP_REFRESHED_FINANCE_SQL = """
DROP TRIGGER IF EXISTS trg_sync_commission_agent_on_ledger
ON finance.ledger_mouvementfinancier;

DROP FUNCTION IF EXISTS finance.sync_commission_agent_from_ledger();
DROP FUNCTION IF EXISTS finance.sync_commission_totale_for_agent(bigint);
DROP FUNCTION IF EXISTS finance.calcul_montant_retirable(bigint);
DROP FUNCTION IF EXISTS finance.calcul_commission_agent(bigint);
"""


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("finance", "0005_align_exam_domain"),
        ("ledger", "0003_align_exam_domain"),
    ]

    operations = [
        migrations.RunSQL(
            sql=REFRESH_FINANCE_SQL,
            reverse_sql=DROP_REFRESHED_FINANCE_SQL,
        ),
    ]
