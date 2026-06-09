# Mini-dossier de conception

## 3.1 Cadrage
### Probleme resolu
L'application gere une tontine numerique simple: rattacher des clients a des agents, ouvrir des cycles d'epargne, enregistrer des depots en nombre de mises, cloturer automatiquement un cycle a 31 collectes, calculer les commissions et autoriser des retraits globaux a partir du montant retirable calcule.

### Utilisateurs concernes
- `ADMIN`: supervision globale, creation des agents, clients et cycles.
- `AGENT`: gestion de son portefeuille de clients, depots et retraits de ses clients.
- `CLIENT`: consultation de ses cycles et de son historique.

### Operations incluses
- Creer un agent.
- Creer un client rattache a un agent.
- Ouvrir un cycle avec une mise valide.
- Enregistrer un depot avec un nombre de mises.
- Cloturer automatiquement a 31 collectes.
- Calculer la retenue, la commission agent, la commission institution et le credit client.
- Effectuer un retrait global.
- Consulter clients, cycles, depots, retraits et mouvements.

### Operations exclues volontairement
- Multi-agence.
- Annulation de mouvements.
- Frais supplementaires hors retenue de cloture.
- Workflow de validation complexe ou double signature.

### Technologie choisie
- `Django` pour le monolithe web, les formulaires, l'admin et les migrations.
- `PostgreSQL` pour la persistance, le schema `finance` et quelques fonctions SQL de support.
- `Tailwind via CDN` pour une interface simple de demonstration.

Cette pile est adaptee a une demarche spec-driven car elle permet de relier clairement regles, modele, services, tests et migrations.

## 3.2 Regles metier
- Un client appartient a un agent.
- Un client peut avoir plusieurs cycles.
- Une mise doit etre positive.
- Une mise doit etre un multiple de 100 FCFA.
- Un cycle commence avec `0` collecte.
- Un cycle demarre avec le statut `EN_COURS`.
- Un depot saisit un nombre de mises positif.
- Le total des collectes ne depasse jamais `31`.
- Un depot cree un mouvement `MISE`.
- A `31` collectes, le cycle est cloture automatiquement.
- La retenue de cloture est egale a une mise.
- La retenue est partagee `50/50` entre l'agent et l'institution.
- Le credit client est egal au total collecte moins la retenue.
- Le montant retirable n'est pas stocke sur le client; il est recalcule depuis les mouvements.
- Un retrait est refuse si le montant retirable calcule est insuffisant.
- Les montants sont manipules en FCFA entiers.

## 3.3 Modele de donnees
### Entites
- `Agent(id, matricule, nom, prenom, telephone, zone, commission_totale, user_id)`
- `Client(id, agent_id, code_client, nom, prenom, telephone, email, adresse, user_id)`
- `Cycle(id, client_id, agent_id, mise, nb_collectes, solde_actuel, statut, type_cloture, date_cloture)`
- `Collecte(id, code, cycle_id, nb_mises, montant, created_at)`
- `Retenue(id, code, cycle_id, montant, commission_agent, commission_institution)`
- `Retrait(id, code, client_id, montant, created_at)`
- `MouvementFinancier(id, cycle_id, client_id, agent_id, type_mouvement, source, destination, montant, created_at)`

### Types de mouvements
- `MISE`
- `RETENUE`
- `COM_AGENT`
- `COM_INSTITUTION`
- `CREDIT_CLIENT`
- `RETRAIT`

## 3.4 Couche metier centrale
La logique metier est centralisee dans deux services Python:
- `accounts.services`: creation d'agents et de clients.
- `finance.services`: ouverture de cycle, depot, cloture automatique, retrait et calcul du montant retirable.

Fonctions principales:
- `create_agent()`
- `create_client()`
- `create_cycle()`
- `create_depot()`
- `close_cycle()`
- `create_retrait()`
- `get_montant_retirable()`

Les operations sont transactionnelles via `@transaction.atomic`. Les vues n'implementent pas les regles; elles appellent les services.

## 3.5 Mini-tracabilite
Le detail est fourni dans `docs/mini_tracabilite.md`.
