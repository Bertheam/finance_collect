# Rapport de tests

## Commande executee
```bash
./venv/bin/python manage.py test accounts finance ledger
```

## Date
- 2026-06-03

## Resultat global
- `12` tests executes
- `12` tests reussis
- `0` echec

## Scenarios verifies
| Scenario | Resultat attendu | Resultat obtenu | Statut |
| --- | --- | --- | --- |
| Creer un cycle avec mise `1000` | Cycle cree | Cycle cree | Reussi |
| Creer un cycle avec mise `1050` | Refuse | Refuse par validation | Reussi |
| Faire un depot de `5` mises | `nb_collectes += 5` et mouvement `MISE` | Conforme | Reussi |
| Faire un depot qui depasse `31` collectes | Refuse | Refuse | Reussi |
| Faire exactement `31` collectes | Cloture automatique | Cycle cloture automatiquement | Reussi |
| Verifier la cloture pour mise `1000` | Retenue `1000`, agent `500`, institution `500`, credit `30000` | Conforme | Reussi |
| Ajouter un depot sur cycle cloture | Refuse | Refuse | Reussi |
| Retirer plus que le montant retirable | Refuse | Refuse | Reussi |
| Retirer un montant disponible | Accepte et diminue le retirable | Conforme | Reussi |
| Recalculer le montant retirable depuis les mouvements | Resultat coherent | Conforme | Reussi |
| Consulter `me` en API | Utilisateur renvoye | Conforme | Reussi |
| Isolation des mouvements d'un client | Seulement ses mouvements visibles | Conforme | Reussi |
