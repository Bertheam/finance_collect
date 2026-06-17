# Finance Collecte System

## Lancer le projet
Ordre standard de démarrage :

```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_exam_data
./venv/bin/python manage.py runserver
```

## Ordre SQL / migrations
- Le chemin normal du projet est : `migrations Django d’abord`, puis `seed`, puis lancement.
- Il n’y a pas de script SQL à exécuter avant les migrations dans le flux standard.
- La source de vérité de la structure est l’historique des migrations Django.

## Comptes et données
- Le jeu minimal est chargé par `seed_exam_data`.
- Sur une base propre, le seeder crée aussi des comptes de démonstration directement utilisables :
  - `iam-admin` / `CollecteAdmin#2026`
  - `iam-agent` / `CollecteAgent#2026`
  - `iam-client` / `CollecteClient#2026`
- Si la base contient déjà des comptes en conflit, le seeder ajoute automatiquement un suffixe au nom d’utilisateur et affiche les identifiants réellement créés dans la sortie console.
- Les comptes applicatifs supplémentaires sont créés via l’interface monolithique.

## Tests
```bash
./venv/bin/python manage.py check
./venv/bin/python manage.py test accounts.tests finance.tests
```

## Livrables
- `docs/matrice_alignement.md`
- `docs/workflow_iam_spec_driven.md`
- `docs/mini_dossier_conception.md`
- `docs/mini_tracabilite.md`
- `docs/rapport_tests.md`
