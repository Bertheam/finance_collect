# Workflow IAM-Spec-Driven

## Objectif
Montrer une demarche de construction pilotee par les regles du besoin, puis tracee jusqu'au code, a la base et aux tests.

## Chaine suivie
1. Besoin metier
2. Regles explicites
3. Modele de donnees
4. Couche metier centrale
5. Interface de demonstration
6. Tests
7. Preuves et livrables

## Application au projet
### 1. Besoin metier
- Gerer des agents
- Gerer des clients
- Ouvrir des cycles
- Enregistrer des depots
- Cloturer automatiquement a 31 collectes
- Calculer les commissions
- Autoriser un retrait global
- Conserver un historique financier justifiable

### 2. Regles explicites
- La mise est positive et multiple de 100
- Un client appartient a un agent
- Un depot est exprime en nombre de mises
- Un cycle ne depasse jamais 31 collectes
- La cloture automatique cree les mouvements attendus
- Le montant retirable se calcule depuis `CREDIT_CLIENT - RETRAIT`

### 3. Traduction dans le modele
- `accounts.Client.agent`
- `finance.Cycle`
- `finance.Collecte.nb_mises`
- `finance.Retenue`
- `finance.Retrait`
- `ledger.MouvementFinancier`

### 4. Traduction dans la couche metier
- `accounts.services.create_agent`
- `accounts.services.create_client`
- `finance.services.create_cycle`
- `finance.services.create_depot`
- `finance.services.close_cycle`
- `finance.services.create_retrait`
- `finance.services.get_montant_retirable`

### 5. Traduction dans la base
- Migrations de structure
- Fonctions SQL de support
- `CHECK CONSTRAINT` sur cycles, depots, retenues, retraits et mouvements

### 6. Traduction dans les tests
- Scenarios obligatoires du sujet couverts dans
  [finance/tests.py](/Users/bertham/Documents/projects/finance_collecte_system/finance/tests.py#L11)
  et
  [ledger/tests.py](/Users/bertham/Documents/projects/finance_collecte_system/ledger/tests.py#L8)

### 7. Preuves
- Matrice d'alignement
- Mini-dossier
- Mini-tracabilite
- Rapport de tests
- Dump SQL
