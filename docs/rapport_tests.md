# Rapport de tests

## Commandes exécutées
```bash
./venv/bin/python manage.py check
./venv/bin/python manage.py test accounts.tests finance.tests
```

## Date
- 2026-06-17

## Résultat global
- `62` tests exécutés
- `62` tests réussis
- `0` échec
- `0` erreur finale

## Scénarios vérifiés
| Scénario | Résultat attendu | Résultat obtenu | Statut |
| --- | --- | --- | --- |
| Créer un cycle avec mise `1000` | Cycle créé | Conforme | Réussi |
| Créer un cycle avec mise non multiple de `100` | Refusé | Conforme | Réussi |
| Faire un dépôt de `5` mises | `nb_collectes += 5` et mouvement `MISE` | Conforme | Réussi |
| Faire un dépôt qui dépasse `31` collectes | Refusé | Conforme | Réussi |
| Faire exactement `31` collectes | Clôture automatique | Conforme | Réussi |
| Vérifier la clôture pour mise `1000` | Retenue `1000`, agent `500`, institution `500`, crédit `30000` | Conforme | Réussi |
| Ajouter un dépôt sur cycle clôturé | Refusé | Conforme | Réussi |
| Retirer plus que le montant retirable calculé | Refusé | Conforme | Réussi |
| Retirer un montant disponible | Retrait accepté et solde retirable diminué | Conforme | Réussi |
| Créer une demande anticipée staff sur cycle en cours | Demande créée | Conforme | Réussi |
| Refuser une demande normale staff dans un contexte invalide | Refusé | Conforme | Réussi |
| Enregistrer un retrait direct staff | Retrait créé | Conforme | Réussi |
| Vérifier les restrictions de navigation côté client | Menus limités, accès back-office refusé | Conforme | Réussi |
| Vérifier le dossier client | Onglet local `Demandes`, absence de doublon `Cycles associés` | Conforme | Réussi |
| Supprimer logiquement un cycle non clôturé | Refusé | Conforme | Réussi |
| Supprimer logiquement un cycle clôturé | Cycle masqué | Conforme | Réussi |
| Supprimer logiquement un client avec cycle en cours | Refusé | Conforme | Réussi |
| Supprimer logiquement un client éligible | Client masqué, cycles clôturés masqués, compte désactivé | Conforme | Réussi |
| Supprimer logiquement un agent avec activité encore ouverte | Refusé | Conforme | Réussi |
| Supprimer logiquement un agent éligible | Agent masqué, clients liés masqués, comptes désactivés | Conforme | Réussi |

## Conclusion
La suite de tests exécutée couvre le noyau métier attendu par le sujet : création des cycles, dépôts, clôture automatique, calculs financiers, retraits, demandes de retrait, restrictions d’accès par rôle et suppression logique sécurisée.
