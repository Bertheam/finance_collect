from django.db import migrations


MOVE_TABLES_TO_FINANCE_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS finance;

DO $$
DECLARE
    table_name text;
    table_names text[] := ARRAY[
        'accounts_agent',
        'accounts_client',
        'accounts_user',
        'accounts_user_groups',
        'accounts_user_user_permissions',
        'auth_group',
        'auth_group_permissions',
        'auth_permission',
        'django_admin_log',
        'django_content_type',
        'django_migrations',
        'django_session',
        'finance_collecte',
        'finance_cycle',
        'ledger_mouvementfinancier'
    ];
BEGIN
    FOREACH table_name IN ARRAY table_names
    LOOP
        IF to_regclass(format('public.%I', table_name)) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I SET SCHEMA finance', table_name);
        END IF;
    END LOOP;
END $$;
"""


RECREATE_FINANCE_ROUTINES = """
CREATE SCHEMA IF NOT EXISTS finance;

CREATE OR REPLACE FUNCTION finance.calcul_solde_reel(p_cycle_id integer)
RETURNS numeric
LANGUAGE plpgsql
AS $function$
DECLARE
    v_entrees numeric := 0;
    v_sorties numeric := 0;
BEGIN
    SELECT COALESCE(SUM(montant), 0)
    INTO v_entrees
    FROM finance.ledger_mouvementfinancier
    WHERE cycle_id = p_cycle_id
      AND destination = 'CYCLE';

    SELECT COALESCE(SUM(montant), 0)
    INTO v_sorties
    FROM finance.ledger_mouvementfinancier
    WHERE cycle_id = p_cycle_id
      AND source = 'CYCLE';

    RETURN v_entrees - v_sorties;
END;
$function$;

CREATE OR REPLACE FUNCTION finance.peut_retirer(p_cycle_id integer)
RETURNS boolean
LANGUAGE plpgsql
AS $function$
DECLARE
    v_solde numeric;
    v_mise numeric;
BEGIN
    SELECT solde_actuel, mise
    INTO v_solde, v_mise
    FROM finance.finance_cycle
    WHERE id = p_cycle_id;

    IF v_solde > v_mise THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$function$;

CREATE OR REPLACE FUNCTION finance.sync_solde_cycle()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    UPDATE finance.finance_cycle
    SET solde_actuel = finance.calcul_solde_reel(NEW.cycle_id)
    WHERE id = NEW.cycle_id;

    RETURN NEW;
END;
$function$;

CREATE OR REPLACE PROCEDURE finance.cloture_normale(IN p_cycle_id integer)
LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_solde numeric;
    v_mise numeric;
    v_montant_client numeric;
BEGIN
    SELECT solde_actuel, mise
    INTO v_solde, v_mise
    FROM finance.finance_cycle
    WHERE id = p_cycle_id
    FOR UPDATE;

    v_montant_client := v_solde - v_mise;

    INSERT INTO finance.ledger_mouvementfinancier (
        cycle_id,
        type_mouvement,
        source,
        destination,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        'MISE_RETENUE',
        'CYCLE',
        'INSTITUTION',
        v_mise / 2,
        NOW()
    );

    INSERT INTO finance.ledger_mouvementfinancier (
        cycle_id,
        type_mouvement,
        source,
        destination,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        'PART_AGENT',
        'CYCLE',
        'AGENT',
        v_mise / 2,
        NOW()
    );

    INSERT INTO finance.ledger_mouvementfinancier (
        cycle_id,
        type_mouvement,
        source,
        destination,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        'RETRAIT_CLIENT',
        'CYCLE',
        'CLIENT',
        v_montant_client,
        NOW()
    );

    UPDATE finance.finance_cycle
    SET
        statut = 'CLOTURE',
        type_cloture = 'NORMALE',
        date_cloture = NOW()
    WHERE id = p_cycle_id;
END;
$procedure$;

CREATE OR REPLACE PROCEDURE finance.retrait_anticipe(IN p_cycle_id integer)
LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_solde numeric;
    v_mise numeric;
    v_montant_client numeric;
BEGIN
    SELECT solde_actuel, mise
    INTO v_solde, v_mise
    FROM finance.finance_cycle
    WHERE id = p_cycle_id
    FOR UPDATE;

    IF v_solde <= v_mise THEN
        RAISE EXCEPTION 'Retrait impossible : solde insuffisant';
    END IF;

    v_montant_client := v_solde - v_mise;

    INSERT INTO finance.ledger_mouvementfinancier (
        cycle_id,
        type_mouvement,
        source,
        destination,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        'PENALITE',
        'CYCLE',
        'INSTITUTION',
        v_mise / 2,
        NOW()
    );

    INSERT INTO finance.ledger_mouvementfinancier (
        cycle_id,
        type_mouvement,
        source,
        destination,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        'PART_AGENT',
        'CYCLE',
        'AGENT',
        v_mise / 2,
        NOW()
    );

    INSERT INTO finance.ledger_mouvementfinancier (
        cycle_id,
        type_mouvement,
        source,
        destination,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        'RETRAIT_CLIENT',
        'CYCLE',
        'CLIENT',
        v_montant_client,
        NOW()
    );

    UPDATE finance.finance_cycle
    SET
        statut = 'CLOTURE',
        type_cloture = 'ANTICIPEE',
        date_cloture = NOW()
    WHERE id = p_cycle_id;
END;
$procedure$;

CREATE OR REPLACE PROCEDURE finance.effectuer_collecte(IN p_cycle_id integer, IN p_montant numeric)
LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_mise numeric;
    v_nb_collectes integer;
    v_statut varchar;
BEGIN
    SELECT mise, nb_collectes, statut
    INTO v_mise, v_nb_collectes, v_statut
    FROM finance.finance_cycle
    WHERE id = p_cycle_id
    FOR UPDATE;

    IF v_statut = 'CLOTURE' THEN
        RAISE EXCEPTION 'Cycle deja cloture';
    END IF;

    IF p_montant <> v_mise THEN
        RAISE EXCEPTION 'Montant invalide';
    END IF;

    IF v_nb_collectes >= 31 THEN
        RAISE EXCEPTION 'Limite de collectes atteinte';
    END IF;

    INSERT INTO finance.finance_collecte (
        cycle_id,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        p_montant,
        NOW()
    );

    INSERT INTO finance.ledger_mouvementfinancier (
        cycle_id,
        type_mouvement,
        source,
        destination,
        montant,
        created_at
    )
    VALUES (
        p_cycle_id,
        'COLLECTE',
        'CLIENT',
        'CYCLE',
        p_montant,
        NOW()
    );

    UPDATE finance.finance_cycle
    SET nb_collectes = nb_collectes + 1
    WHERE id = p_cycle_id;

    IF (
        SELECT nb_collectes
        FROM finance.finance_cycle
        WHERE id = p_cycle_id
    ) >= 31 THEN
        CALL finance.cloture_normale(p_cycle_id);
    END IF;
END;
$procedure$;

DO $$
BEGIN
    IF to_regclass('finance.ledger_mouvementfinancier') IS NOT NULL THEN
        EXECUTE 'DROP TRIGGER IF EXISTS trg_sync_solde_cycle ON finance.ledger_mouvementfinancier';
        EXECUTE '
            CREATE TRIGGER trg_sync_solde_cycle
            AFTER INSERT ON finance.ledger_mouvementfinancier
            FOR EACH ROW
            EXECUTE FUNCTION finance.sync_solde_cycle()
        ';
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('ledger', '0002_remove_mouvementfinancier_agent_and_more'),
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=MOVE_TABLES_TO_FINANCE_SCHEMA,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=RECREATE_FINANCE_ROUTINES,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
