# Mini-dossier de conception

## 3.1 Cadrage

### Problème résolu
L’application permet de gérer une tontine numérique simple autour d’un portefeuille client piloté par des agents. Elle couvre l’ouverture des cycles, la collecte des mises, la clôture automatique à 31 collectes, le calcul des commissions, la production des mouvements financiers, les retraits globaux et la gestion des demandes de retrait.

### Utilisateurs concernés
- `ADMIN` : supervise l’ensemble du référentiel, crée les agents, clients et cycles, valide ou rejette les demandes, exécute les retraits, masque les éléments supprimés logiquement.
- `AGENT` : gère uniquement ses clients, leurs cycles, les dépôts, les demandes de retrait et les retraits autorisés.
- `CLIENT` : consulte ses cycles, son montant retirable, ses demandes et ses retraits ; il peut soumettre une demande de retrait s’il dispose d’un compte.

### Opérations incluses dans la version actuelle
- créer un agent ;
- créer un client rattaché à un agent ;
- créer automatiquement un compte agent ;
- créer optionnellement un compte client ;
- ouvrir un cycle avec mise valide ;
- enregistrer un dépôt en nombre de mises ;
- clôturer automatiquement un cycle à 31 collectes ;
- calculer la retenue, la commission agent, la commission institution et le crédit client ;
- recalculer le montant retirable à partir des mouvements financiers ;
- exécuter un retrait direct si le montant retirable est disponible ;
- créer, valider, rejeter et exécuter une demande de retrait ;
- notifier les acteurs concernés ;
- désactiver un compte agent ou client ;
- supprimer logiquement un cycle clôturé, un client ou un agent selon des règles de sécurité.

### Opérations volontairement exclues
- multi-agence ;
- annulation d’écriture financière ;
- édition manuelle des commissions ;
- suppression physique des écritures ;
- moteur de workflow complexe ;
- API publique dédiée : l’objectif retenu est un monolithe web léger.

### Stack retenue
- `Django` pour le monolithe, les formulaires, les vues, les services, les migrations et l’authentification ;
- `PostgreSQL` pour la persistance ;
- schéma `finance` pour l’alignement base demandé ;
- `Tailwind CSS` via CDN pour l’interface de démonstration.

Cette pile est adaptée à une démarche spec-driven car elle permet de relier directement besoin métier, validation, persistance, services transactionnels, interface et tests.

## 3.2 Règles métier respectées
- Un client appartient à un agent.
- Un client peut avoir plusieurs cycles.
- Un agent ne voit et n’opère que sur son portefeuille.
- Une mise doit être positive.
- Une mise doit être un multiple de 100 FCFA.
- Un cycle démarre avec `0` collecte et le statut `EN_COURS`.
- Un dépôt saisit un nombre de mises strictement positif.
- Le total des collectes ne dépasse jamais `31`.
- Un dépôt crée un mouvement `MISE`.
- À `31` collectes, le cycle est clôturé automatiquement.
- La retenue de clôture est égale à une mise.
- La retenue est partagée `50 % / 50 %` entre l’agent et l’institution.
- Le crédit client est égal au total collecté moins la retenue.
- Le montant retirable est calculé à partir des mouvements `CREDIT_CLIENT` et `RETRAIT`.
- Un retrait est refusé si le montant retirable calculé est insuffisant.
- Une demande anticipée nécessite un cycle `EN_COURS`.
- Une demande normale nécessite un cycle `CLOTURE`.
- Un agent ou un admin peut opérer pour un client de son portefeuille sans exposer la logique métier dans la vue.
- Un cycle clôturé peut être masqué logiquement ; un cycle en cours ne le peut pas.
- Un client ou un agent ayant encore des cycles en cours ne peut pas être supprimé logiquement.
- Les suppressions logiques masquent les éléments des listes applicatives sans effacer l’historique financier.
- Les montants sont manipulés en entiers FCFA.

## 3.3 Modèle de données actuel

### Entités métier principales
- `accounts.User` : utilisateur applicatif avec rôle `ADMIN`, `AGENT` ou `CLIENT`.
- `accounts.Agent` : agent métier, total de commission, compte lié optionnel, suppression logique.
- `accounts.Client` : client métier, agent responsable, compte lié optionnel, suppression logique.
- `finance.Cycle` : cycle d’épargne, mise, nombre de collectes, solde du cycle, statut, clôture, suppression logique.
- `finance.Collecte` : dépôt exprimé en `nb_mises` avec montant calculé.
- `finance.Retenue` : retenue de clôture et répartition des commissions.
- `finance.Retrait` : retrait global exécuté.
- `finance.DemandeRetrait` : demande anticipée ou normale, avec statut de traitement.
- `ledger.MouvementFinancier` : historique financier justificatif.
- `accounts.Notification` : notification applicative pour staff et client.

### Relations structurantes
- `Client -> Agent` : obligatoire.
- `Cycle -> Client` : obligatoire.
- `Cycle -> Agent` : obligatoire et cohérent avec l’agent du client.
- `Collecte -> Cycle` : obligatoire.
- `Retenue -> Cycle` : relation un-à-un.
- `Retrait -> Client` : obligatoire.
- `DemandeRetrait -> Cycle` et `DemandeRetrait -> Client` : obligatoires et cohérents.
- `MouvementFinancier` : rattaché au cycle pour les écritures de cycle, au client pour les retraits, et à l’agent lorsque nécessaire.

### Types de mouvements réellement utilisés
- `MISE`
- `RETENUE`
- `COM_AGENT`
- `COM_INSTITUTION`
- `CREDIT_CLIENT`
- `RETRAIT`

## 3.4 Couche métier centrale
La logique métier n’est pas dispersée dans les vues. Elle est centralisée dans des services Python transactionnels.

### Services principaux
- `accounts.services`
  - `create_agent()`
  - `create_client()`
  - `create_notification()`
  - `soft_delete_agent()`
  - `soft_delete_client()`
- `finance.services`
  - `create_cycle()`
  - `create_depot()`
  - `close_cycle()`
  - `create_retrait()`
  - `get_montant_retirable()`
  - `create_demande_retrait()`
  - `approve_demande_retrait()`
  - `reject_demande_retrait()`
  - `execute_retrait_from_demande()`
  - `soft_delete_cycle()`

### Pourquoi la logique métier est en Python et non en procédures SQL
Le sujet demande une couche métier centrale, pas nécessairement une implémentation en procédures stockées. Le choix Python a été retenu pour les raisons suivantes :
- l’application est un monolithe léger Django ; les services Python s’intègrent naturellement aux vues, formulaires, ACL et notifications ;
- les règles métier deviennent plus faciles à tester finement avec `manage.py test` ;
- les transactions restent explicites avec `@transaction.atomic` ;
- les services peuvent combiner validation métier, écritures financières, notifications et sécurité d’accès, ce qu’une procédure SQL pure gérerait moins proprement dans cette architecture ;
- l’interface ne recalcule pas les règles : elle appelle les services, ce qui respecte strictement le principe du sujet.

Le schéma SQL `finance` reste néanmoins pris en charge pour la structure et la sauvegarde. Le projet conserve aussi des fonctions SQL utilitaires pour le recalcul et la synchronisation de la commission agent, mais l’orchestration métier principale est volontairement portée par les services Python.

## 3.5 Durcissement des données

### Validations métier côté modèle et service
- `Cycle.clean()` vérifie le multiple de 100, la borne `0..31` sur les collectes et la cohérence agent/client.
- `Collecte.clean()` impose `montant = mise * nb_mises`.
- `Retenue.clean()` impose `montant = commission_agent + commission_institution`.
- `MouvementFinancier.clean()` impose les rattachements obligatoires selon le type de mouvement.
- `DemandeRetrait.clean()` impose la cohérence client/cycle et un montant positif si renseigné.

### Contraintes SQL et schéma
- Le schéma cible est `finance`.
- Le modèle `DemandeRetrait` porte des `CheckConstraint` sur le montant, le type et le statut.
- Le total `commission_totale` de l’agent est synchronisé à partir des mouvements `COM_AGENT`.
- Les colonnes `deleted_at` et `deleted_by` matérialisent la suppression logique sur `Agent`, `Client` et `Cycle`.

## 3.6 Vues et comportement applicatif
- Les listes et détails masquent les éléments supprimés logiquement.
- Les actions critiques sont filtrées par rôle et par portée métier.
- Les formulaires n’acceptent plus les agents ou clients déjà masqués.
- Le header expose les notifications staff et les demandes en attente.
- Chaque rôle voit une interface utile et allégée : l’admin garde le pilotage global, l’agent ne voit que son portefeuille et le client n’accède qu’à ses cycles, ses demandes et ses retraits.
- Le dashboard client a été volontairement simplifié pour ne conserver que les indicateurs utiles et les cycles récents.

## 3.7 Jeu de données minimal et exécution
### Jeu minimal fourni
La commande `seed_exam_data` charge :
- un compte admin `iam-admin` ;
- un agent `AG-IAM-1` ;
- un compte agent `iam-agent` ;
- un client `CL-AMINATA-001` ;
- un compte client `iam-client` ;
- un cycle à `1000 FCFA` clôturé automatiquement à `31` collectes ;
- un retrait global si le montant retirable est suffisant.

Sur une base propre, ces identifiants sont créés tels quels. Si la base contient déjà des comptes en conflit, la commande conserve un comportement idempotent et affiche les identifiants effectivement retenus.

### Commandes utiles
```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_exam_data
./venv/bin/python manage.py runserver
```

## 3.8 État de validation
Au moment de cette mise à jour :
- les migrations de suppression logique ont été appliquées ;
- les tests métier `accounts.tests` et `finance.tests` passent ;
- `62` tests ont été exécutés avec succès ;
- la documentation a été réalignée sur l’état réel du code et de la base.
