from django.db import migrations


RECREATE_FINANCE_ROUTINES_WITH_BIGINT = """
DROP TRIGGER IF EXISTS trg_sync_solde_cycle
ON finance.ledger_mouvementfinancier;

DROP FUNCTION IF EXISTS finance.sync_solde_cycle();
DROP FUNCTION IF EXISTS finance.peut_retirer(integer);
DROP FUNCTION IF EXISTS finance.calcul_solde_reel(integer);
DROP PROCEDURE IF EXISTS finance.effectuer_collecte(integer, numeric);
DROP PROCEDURE IF EXISTS finance.retrait_anticipe(integer);
DROP PROCEDURE IF EXISTS finance.cloture_normale(integer);

CREATE OR REPLACE FUNCTION finance.calcul_solde_reel(p_cycle_id bigint)
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

CREATE OR REPLACE FUNCTION finance.peut_retirer(p_cycle_id bigint)
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

CREATE OR REPLACE PROCEDURE finance.cloture_normale(IN p_cycle_id bigint)
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

CREATE OR REPLACE PROCEDURE finance.retrait_anticipe(IN p_cycle_id bigint)
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

CREATE OR REPLACE PROCEDURE finance.effectuer_collecte(IN p_cycle_id bigint, IN p_montant numeric)
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

CREATE TRIGGER trg_sync_solde_cycle
AFTER INSERT ON finance.ledger_mouvementfinancier
FOR EACH ROW
EXECUTE FUNCTION finance.sync_solde_cycle();
"""


REVERSE_TO_INTEGER_SIGNATURES = """
DROP TRIGGER IF EXISTS trg_sync_solde_cycle
ON finance.ledger_mouvementfinancier;

DROP FUNCTION IF EXISTS finance.sync_solde_cycle();
DROP FUNCTION IF EXISTS finance.peut_retirer(bigint);
DROP FUNCTION IF EXISTS finance.calcul_solde_reel(bigint);
DROP PROCEDURE IF EXISTS finance.effectuer_collecte(bigint, numeric);
DROP PROCEDURE IF EXISTS finance.retrait_anticipe(bigint);
DROP PROCEDURE IF EXISTS finance.cloture_normale(bigint);

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
    SET solde_actuel = finance.calcul_solde_reel(NEW.cycle_id::integer)
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

CREATE TRIGGER trg_sync_solde_cycle
AFTER INSERT ON finance.ledger_mouvementfinancier
FOR EACH ROW
EXECUTE FUNCTION finance.sync_solde_cycle();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_sync_agent_commissions'),
    ]

    operations = [
        migrations.RunSQL(
            sql=RECREATE_FINANCE_ROUTINES_WITH_BIGINT,
            reverse_sql=REVERSE_TO_INTEGER_SIGNATURES,
        ),
    ]
