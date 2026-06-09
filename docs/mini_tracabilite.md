# Mini-tracabilite

| Regle metier | Emplacement code | Test associe |
| --- | --- | --- |
| Mise positive | `finance/services.py:create_cycle` | `test_create_cycle_with_valid_mise_is_accepted` |
| Mise multiple de 100 | `finance/services.py:_require_multiple_of_100`, `finance/models.py:Cycle.clean` | `test_create_cycle_with_non_multiple_of_100_is_refused` |
| Depot en nb de mises | `finance/services.py:create_depot` | `test_depot_of_five_mises_increments_collectes_and_creates_mise` |
| Max 31 collectes | `finance/services.py:create_depot` | `test_depot_exceeding_31_collectes_is_refused` |
| Cloture automatique a 31 | `finance/services.py:create_depot`, `finance/services.py:close_cycle` | `test_exactly_31_collectes_closes_cycle_automatically` |
| Retenue egale a une mise | `finance/services.py:close_cycle`, `finance/models.py:Retenue.clean` | `test_exactly_31_collectes_closes_cycle_automatically` |
| Commission agent 50% | `finance/services.py:close_cycle` | `test_exactly_31_collectes_closes_cycle_automatically` |
| Credit client calcule | `finance/services.py:close_cycle` | `test_exactly_31_collectes_closes_cycle_automatically` |
| Depot interdit sur cycle cloture | `finance/services.py:create_depot` | `test_closed_cycle_refuses_new_depot` |
| Retrait refuse si insuffisant | `finance/services.py:create_retrait` | `test_retrait_larger_than_withdrawable_is_refused` |
| Montant retirable depuis mouvements | `finance/services.py:get_montant_retirable`, `finance` SQL `calcul_montant_retirable` | `test_retrait_available_amount_is_accepted_and_decreases_withdrawable` |
| Visibilite des mouvements par client | `ledger/views.py` | `ledger.tests.LedgerApiTests.test_client_only_sees_own_mouvements` |
