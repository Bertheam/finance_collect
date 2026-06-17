# Mini-traçabilité

| Règle métier | Où est-elle appliquée ? | Test prévu / réalisé |
| --- | --- | --- |
| Une mise doit être positive | `finance.services.create_cycle()` | `finance.tests.FinanceDomainTests.test_create_cycle_with_valid_mise_is_accepted` |
| Une mise doit être un multiple de 100 FCFA | `finance.services._require_multiple_of_100()`, `finance.models.Cycle.clean()` | `finance.tests.FinanceDomainTests.test_create_cycle_with_non_multiple_of_100_is_refused` |
| Un dépôt utilise un nombre de mises positif | `finance.services.create_depot()` | `finance.tests.FinanceDomainTests.test_depot_of_five_mises_increments_collectes_and_creates_mise` |
| Le total des collectes ne dépasse jamais 31 | `finance.services.create_depot()` | `finance.tests.FinanceDomainTests.test_depot_exceeding_31_collectes_is_refused` |
| À 31 collectes, le cycle est clôturé automatiquement | `finance.services.create_depot()`, `finance.services.close_cycle()` | `finance.tests.FinanceDomainTests.test_exactly_31_collectes_closes_cycle_automatically` |
| La retenue de clôture est égale à une mise | `finance.services.close_cycle()`, `finance.models.Retenue.clean()` | `finance.tests.FinanceDomainTests.test_exactly_31_collectes_closes_cycle_automatically` |
| La commission agent vaut 50 % de la retenue | `finance.services.close_cycle()` | `finance.tests.FinanceDomainTests.test_exactly_31_collectes_closes_cycle_automatically` |
| Le montant retirable vient des mouvements | `finance.services.get_montant_retirable()`, `ledger.models.MouvementFinancier` | `finance.tests.FinanceDomainTests.test_retrait_available_amount_is_accepted_and_decreases_withdrawable` |
| Un retrait est refusé si le montant retirable est insuffisant | `finance.services.create_retrait()` | `finance.tests.FinanceDomainTests.test_retrait_larger_than_withdrawable_is_refused` |
| Une demande anticipée exige un cycle en cours | `finance.services.create_demande_retrait()` | `accounts.tests.MonolithPagesTests.test_staff_can_create_anticipatory_request_for_client_without_account` |
| Une demande normale staff depuis un cycle en cours est refusée | `config.web_views.CycleDemandeRetraitView`, `finance.services.create_demande_retrait()` | `accounts.tests.MonolithPagesTests.test_staff_cannot_create_normal_request_from_cycle_detail` |
| Un retrait direct staff doit créer un vrai retrait | `config.web_views.CycleDirectRetraitView`, `finance.services.create_retrait()` | `accounts.tests.MonolithPagesTests.test_staff_can_register_direct_withdrawal_from_cycle_detail` |
| Un client ne doit pas accéder aux écrans back-office | `config.web_views.RoleRequiredMixin`, filtres de navigation par rôle | `accounts.tests.MonolithPagesTests.test_client_cannot_access_backoffice_pages_and_sees_limited_navigation` |
| Le dossier client ne doit pas dupliquer les cycles déjà présents dans le menu principal | `templates/clients/detail.html`, `config.web_views.ClientDetailView` | `accounts.tests.MonolithPagesTests.test_client_detail_replaces_local_cycles_tab_with_demandes` |
| Un cycle clôturé seul peut être supprimé logiquement | `finance.services.soft_delete_cycle()` | `finance.tests.FinanceDomainTests.test_soft_delete_cycle_requires_closed_status`, `finance.tests.FinanceDomainTests.test_soft_delete_cycle_masks_closed_cycle` |
| Un client avec cycle en cours ne peut pas être supprimé logiquement | `accounts.services.soft_delete_client()` | `accounts.tests.MonolithPagesTests.test_soft_delete_client_requires_no_open_cycle` |
| Un agent avec client ayant un cycle en cours ne peut pas être supprimé logiquement | `accounts.services.soft_delete_agent()` | `accounts.tests.MonolithPagesTests.test_soft_delete_agent_requires_no_open_cycle` |
| Une suppression logique masque les données et désactive les comptes liés | `accounts.services.soft_delete_client()`, `accounts.services.soft_delete_agent()` | `accounts.tests.MonolithPagesTests.test_soft_delete_client_masks_closed_cycles_and_deactivates_account`, `accounts.tests.MonolithPagesTests.test_soft_delete_agent_masks_linked_closed_data_and_deactivates_accounts` |
