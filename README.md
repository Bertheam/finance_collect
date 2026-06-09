# Finance Collecte System

## Lancer le projet
```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_exam_data
./venv/bin/python manage.py runserver
```

## Comptes et donnees
- Le jeu minimal est charge par `seed_exam_data`.
- L'admin Django peut etre utilise pour completer le referentiel.

## Tests
```bash
./venv/bin/python manage.py test accounts finance ledger
```

## Livrables
- `docs/matrice_alignement.md`
- `docs/workflow_iam_spec_driven.md`
- `docs/mini_dossier_conception.md`
- `docs/mini_tracabilite.md`
- `docs/rapport_tests.md`
