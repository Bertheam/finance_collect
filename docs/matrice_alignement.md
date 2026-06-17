# Matrice d’alignement sujet / projet

| Attendu du sujet | Implémentation projet | Preuve | Statut |
| --- | --- | --- | --- |
| Gérer les agents | Modèle `Agent`, vues liste/détail, création, activation/désactivation, suppression logique | `accounts/models.py`, `config/web_views.py`, `templates/agents/*` | Conforme |
| Gérer les clients | Modèle `Client`, vues liste/détail, création, compte optionnel, suppression logique | `accounts/models.py`, `accounts/services.py`, `templates/clients/*` | Conforme |
| Gérer les cycles d’épargne | Modèle `Cycle`, création par service, détail, dépôts | `finance/models.py`, `finance/services.py`, `templates/cycles/*` | Conforme |
| Enregistrer les dépôts | `create_depot()` avec contrôle métier et mouvement `MISE` | `finance/services.py` | Conforme |
| Clôturer automatiquement à 31 collectes | Déclenché dans `create_depot()` puis `close_cycle()` | `finance/services.py`, tests finance | Conforme |
| Calculer commissions et retenue | `close_cycle()` produit `Retenue`, `COM_AGENT`, `COM_INSTITUTION`, `CREDIT_CLIENT` | `finance/services.py` | Conforme |
| Retrait global client | `create_retrait()` + vues staff | `finance/services.py`, `config/web_views.py` | Conforme |
| Gérer les demandes de retrait | `DemandeRetrait`, vues staff, création client ou staff selon le contexte, validation, rejet, exécution | `finance/models.py`, `finance/services.py`, `templates/demandes/*`, `templates/cycles/detail.html` | Conforme |
| Historique financier par mouvements | `ledger.MouvementFinancier` et vue `mouvements` | `ledger/models.py`, `templates/mouvements/list.html` | Conforme |
| Montant retirable calculé depuis les mouvements | `get_montant_retirable()` | `finance/services.py` | Conforme |
| Couche métier centrale | Services Python transactionnels, vues minces | `accounts/services.py`, `finance/services.py` | Conforme |
| Règles métier hors interface | Les vues appellent les services ; pas de recalcul métier dans les templates | `config/web_views.py` | Conforme |
| ACL et vues adaptées au rôle | Menus, listes, filtres et actions réduits selon `ADMIN`, `AGENT`, `CLIENT` | `config/web_views.py`, `accounts/permissions.py`, `templates/base.html`, `templates/dashboard.html` | Conforme |
| Tests obligatoires | Suite `accounts.tests` et `finance.tests` exécutée avec succès | `docs/rapport_tests.md` | Conforme |
| Jeu de données minimum | Commande `seed_exam_data` | `finance/management/commands/seed_exam_data.py` | Conforme |
| Livrable de conception | Mini-dossier et mini-traçabilité | `docs/mini_dossier_conception.md`, `docs/mini_tracabilite.md` | Conforme |
| Base structurée dans le schéma `finance` | Migrations Django + SQL embarqué dans les migrations | `finance/migrations/0002_*`, `finance/migrations/0006_*` | Conforme |
| Suppression sécurisée | Suppression logique avec `deleted_at`, `deleted_by` et masquage applicatif | `accounts/models.py`, `finance/models.py`, services et vues | Conforme |
