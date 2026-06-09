from django.db import migrations


SYNC_AGENT_COMMISSIONS = """
CREATE OR REPLACE FUNCTION finance.calcul_commission_agent(p_agent_id bigint)
RETURNS numeric
LANGUAGE plpgsql
AS $function$
DECLARE
    v_total numeric := 0;
BEGIN
    SELECT COALESCE(SUM(m.montant), 0)
    INTO v_total
    FROM finance.ledger_mouvementfinancier AS m
    JOIN finance.finance_cycle AS c
      ON c.id = m.cycle_id
    WHERE c.agent_id = p_agent_id
      AND m.type_mouvement = 'PART_AGENT'
      AND m.destination = 'AGENT';

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
        SELECT agent_id
        INTO v_old_agent_id
        FROM finance.finance_cycle
        WHERE id = OLD.cycle_id;
    END IF;

    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT agent_id
        INTO v_new_agent_id
        FROM finance.finance_cycle
        WHERE id = NEW.cycle_id;
    END IF;

    PERFORM finance.sync_commission_totale_for_agent(v_old_agent_id);

    IF v_new_agent_id IS DISTINCT FROM v_old_agent_id THEN
        PERFORM finance.sync_commission_totale_for_agent(v_new_agent_id);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$function$;

CREATE OR REPLACE FUNCTION finance.sync_commission_agent_from_cycle()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.agent_id IS DISTINCT FROM OLD.agent_id THEN
        PERFORM finance.sync_commission_totale_for_agent(OLD.agent_id);
        PERFORM finance.sync_commission_totale_for_agent(NEW.agent_id);
    END IF;

    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_sync_commission_agent_on_ledger
ON finance.ledger_mouvementfinancier;

CREATE TRIGGER trg_sync_commission_agent_on_ledger
AFTER INSERT OR UPDATE OR DELETE
ON finance.ledger_mouvementfinancier
FOR EACH ROW
EXECUTE FUNCTION finance.sync_commission_agent_from_ledger();

DROP TRIGGER IF EXISTS trg_sync_commission_agent_on_cycle
ON finance.finance_cycle;

CREATE TRIGGER trg_sync_commission_agent_on_cycle
AFTER UPDATE OF agent_id
ON finance.finance_cycle
FOR EACH ROW
EXECUTE FUNCTION finance.sync_commission_agent_from_cycle();

UPDATE finance.accounts_agent AS agent
SET commission_totale = finance.calcul_commission_agent(agent.id);
"""


DROP_AGENT_COMMISSION_SYNC = """
DROP TRIGGER IF EXISTS trg_sync_commission_agent_on_cycle
ON finance.finance_cycle;

DROP TRIGGER IF EXISTS trg_sync_commission_agent_on_ledger
ON finance.ledger_mouvementfinancier;

DROP FUNCTION IF EXISTS finance.sync_commission_agent_from_cycle();
DROP FUNCTION IF EXISTS finance.sync_commission_agent_from_ledger();
DROP FUNCTION IF EXISTS finance.sync_commission_totale_for_agent(bigint);
DROP FUNCTION IF EXISTS finance.calcul_commission_agent(bigint);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_move_tables_to_finance_schema'),
    ]

    operations = [
        migrations.RunSQL(
            sql=SYNC_AGENT_COMMISSIONS,
            reverse_sql=DROP_AGENT_COMMISSION_SYNC,
        ),
    ]
