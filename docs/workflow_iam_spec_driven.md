# Workflow IAM-Spec-Driven

## Objectif
Montrer une démarche de construction pilotée par les règles du besoin, puis tracée jusqu’au code, à la base et aux tests.

## Chaîne suivie
1. Besoin métier
2. Règles explicites
3. Modèle de données
4. Couche métier centrale
5. Interface de démonstration
6. Tests
7. Preuves et livrables

## Application au projet
### 1. Besoin métier
- Gérer des agents
- Gérer des clients
- Ouvrir des cycles
- Enregistrer des dépôts
- Clôturer automatiquement à 31 collectes
- Calculer les commissions
- Autoriser un retrait global
- Gérer les demandes de retrait
- Conserver un historique financier justifiable

### 2. Règles explicites
- La mise est positive et multiple de 100
- Un client appartient à un agent
- Un dépôt est exprimé en nombre de mises
- Un cycle ne dépasse jamais 31 collectes
- La clôture automatique crée les mouvements attendus
- Le montant retirable se calcule depuis `CREDIT_CLIENT - RETRAIT`
- Les rôles n’ont accès qu’aux écrans et actions qui leur sont utiles

### 3. Traduction dans le modèle
- `accounts.Client.agent`
- `finance.Cycle`
- `finance.Collecte.nb_mises`
- `finance.Retenue`
- `finance.Retrait`
- `finance.DemandeRetrait`
- `ledger.MouvementFinancier`

### 4. Traduction dans la couche métier
- `accounts.services.create_agent`
- `accounts.services.create_client`
- `finance.services.create_cycle`
- `finance.services.create_depot`
- `finance.services.close_cycle`
- `finance.services.create_retrait`
- `finance.services.create_demande_retrait`
- `finance.services.approve_demande_retrait`
- `finance.services.reject_demande_retrait`
- `finance.services.execute_retrait_from_demande`
- `finance.services.get_montant_retirable`

### 5. Traduction dans la base
- Migrations de structure
- Fonctions SQL de support
- `CHECK CONSTRAINT` sur cycles, dépôts, retenues, retraits, demandes et mouvements

### 6. Traduction dans les tests
- Scénarios obligatoires du sujet couverts dans
  [finance/tests.py](/Users/bertham/Documents/projects/finance_collecte_system/finance/tests.py#L11)
  et
  [accounts/tests.py](/Users/bertham/Documents/projects/finance_collecte_system/accounts/tests.py#L11)

### 7. Preuves
- Matrice d'alignement
- Mini-dossier
- Mini-traçabilité
- Rapport de tests
- Historique des migrations
