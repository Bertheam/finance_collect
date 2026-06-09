# Création du projet Django — Système de Collecte Financière

# 1. Prérequis

Installer :
- Python 3.12+
- PostgreSQL
- Git
- Docker (optionnel)
- VS Code ou PyCharm

---

# 2. Création du dossier projet

```bash
mkdir finance_collecte_system
cd finance_collecte_system
```

---

# 3. Création de l’environnement virtuel

## Linux / Mac

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

---

# 4. Installation des dépendances principales

```bash
pip install django
pip install djangorestframework
pip install psycopg2-binary
pip install djangorestframework-simplejwt
pip install pyotp
pip install django-otp
pip install python-decouple
```

---

# 5. Création du projet Django

```bash
django-admin startproject config .
```

---

# 6. Structure initiale

```text
finance_collecte_system/
│
├── config/
├── venv/
├── manage.py
└── requirements.txt
```

---

# 7. Sauvegarde des dépendances

```bash
pip freeze > requirements.txt
```

---

# 8. Création des applications métier

## Application comptes/authentification

```bash
python manage.py startapp accounts
```

---

## Application finance

```bash
python manage.py startapp finance
```

---

## Application mouvements financiers

```bash
python manage.py startapp ledger
```

---

# 9. Nouvelle structure projet

```text
finance_collecte_system/
│
├── accounts/
├── finance/
├── ledger/
├── config/
├── manage.py
├── requirements.txt
└── venv/
```

---

# 10. Création de la base PostgreSQL

Se connecter PostgreSQL :

```bash
psql -U postgres
```

---

Créer la base :

```sql
CREATE DATABASE finance_collecte;
```

---

Créer utilisateur :

```sql
CREATE USER finance_user WITH PASSWORD 'finance_password';
```

---

Donner les droits :

```sql
GRANT ALL PRIVILEGES ON DATABASE finance_collecte TO finance_user;
```

---

# 11. Configuration PostgreSQL dans Django

Modifier :

```text
config/settings.py
```

---

## DATABASES

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'finance_collecte',
        'USER': 'finance_user',
        'PASSWORD': 'finance_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

# 12. Ajouter les applications installées

Dans :

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'django_otp',

    'accounts',
    'finance',
    'ledger',
]
```

---

# 13. Configuration DRF + JWT

Toujours dans settings.py

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}
```

---

# 14. Première migration

```bash
python manage.py migrate
```

---

# 15. Création du super utilisateur

```bash
python manage.py createsuperuser
```

---

# 16. Lancement du serveur

```bash
python manage.py runserver
```

---

# 17. Vérification

Accéder :

```text
http://127.0.0.1:8000/
```

Admin Django :

```text
http://127.0.0.1:8000/admin/
```

---

# 18. Architecture métier recommandée

```text
accounts/
    authentication
    MFA
    utilisateurs

finance/
    cycles
    collectes
    retraits
    orchestration métier

ledger/
    mouvements financiers
    audit
    projections de soldes
```

---

# 19. Philosophie architecture

## PostgreSQL
Contient :
- contraintes
- triggers
- procédures
- fonctions métiers
- vérité financière

---

## Django
Contient :
- API REST
- authentification
- MFA
- orchestration applicative
- services backend

---

## Frontend
Contient uniquement :
- affichage
- saisie utilisateur
- consultation

---

# 20. Étape suivante recommandée

Après création du projet :

1. Concevoir les modèles Django
2. Concevoir les tables PostgreSQL métier
3. Implémenter les mouvements financiers
4. Implémenter les procédures PL/pgSQL
5. Implémenter les APIs DRF
6. Ajouter JWT + MFA
7. Ajouter les triggers PostgreSQL

