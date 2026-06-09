# Matrice d'alignement sujet / projet

| Exigence du sujet | Etat initial constate | Correction appliquee | Etat final |
| --- | --- | --- | --- |
| Un client appartient a un agent | Absent du modele `Client` | Ajout de `Client.agent` + backfill migration + controles de creation | Conforme |
| Un client peut avoir plusieurs cycles | Deja present | Conservation du lien `Client -> Cycle` | Conforme |
| La mise est positive | Controle incomplet | Validation service `create_cycle()` + `Cycle.clean()` | Conforme |
| La mise est un multiple de 100 FCFA | Absent | Validation service + `Cycle.clean()` | Conforme |
| Le cycle commence avec 0 collecte | Deja vise mais non trace explicitement | Initialisation centralisee dans `create_cycle()` | Conforme |
| Le cycle demarre avec le statut `EN_COURS` | Deja present | Centralisation dans `create_cycle()` | Conforme |
| Un depot correspond a une ou plusieurs mises | Non conforme: ancienne collecte au montant unitaire | Remplacement par `nb_mises` + calcul `montant = mise * nb_mises` | Conforme |
| Le total des collectes ne depasse jamais 31 | Partiellement couvert par ancienne procedure | Regle centralisee dans `create_depot()` + tests obligatoires | Conforme |
| Un depot cree un mouvement `MISE` | Ancien type `COLLECTE` | Typologie des mouvements remplacee par `MISE` | Conforme |
| A 31 collectes, cloture automatique | Deja partiellement present | `close_cycle()` declenchee automatiquement par `create_depot()` | Conforme |
| Retenue = une mise | Ancienne logique differente de nommage | `Retenue` + mouvement `RETENUE` | Conforme |
| Commission agent = retenue / 2 | Ancienne logique `PART_AGENT` | `COM_AGENT` + recalcul commission agent | Conforme |
| Commission institution = retenue / 2 | Ancienne logique `PART_INSTITUTION` | `COM_INSTITUTION` | Conforme |
| Credit client = total collecte - retenue | Ancien type `RETRAIT_CLIENT` ambigu | Mouvement `CREDIT_CLIENT` explicite | Conforme |
| Retrait global client | Absent | Ajout du modele `Retrait`, service `create_retrait()`, vues et API | Conforme |
| Montant retirable = total(CREDIT_CLIENT) - total(RETRAIT) | Absent cote client | Service `get_montant_retirable()` + fonction SQL `finance.calcul_montant_retirable()` | Conforme |
| Historique financier lisible | Partiel | Vue monolithique `/mouvements/` + API `/api/mouvements/` | Conforme |
| Interface = saisie/affichage uniquement | Ancienne UI melangee a l'ancien contrat | Toutes les regles critiques basculees dans `accounts.services` et `finance.services` | Conforme |
| Couche metier centrale expose createClient/createCycle/createDepot/createRetrait/getMontantRetirable | Incomplet | Services metier explicites ajoutes | Conforme |
| Toute regle critique a au moins un test | Insuffisant | 12 tests dont scenarios obligatoires du sujet | Conforme |
| Jeu de donnees minimum | Absent | Commande `python manage.py seed_exam_data` | Conforme |
| Livrables spec-driven | Absent | Mini-dossier, traceabilite, rapport de tests, matrice | Conforme |

## Fichiers pivots
- `accounts/services.py`
- `finance/services.py`
- `config/web_views.py`
- `finance/tests.py`
- `docs/mini_dossier_conception.md`
