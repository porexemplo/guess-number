# Devine Nombre Dapp

Projet complet **from scratch** avec :
- **4 smart contracts Solidity**
- **backend Python / Flask + web3.py**
- **frontend HTML/CSS/JS**
- prévu pour **Ganache local**

## Structure

- `backend.py`
- `requirements.txt`
- `contracts/GuessNumberV1.sol`
- `contracts/GuessNumberV2.sol`
- `contracts/GuessNumberV3.sol`
- `contracts/GuessNumberV4.sol`
- `frontend/index.html`
- `frontend/style.css`
- `frontend/app.js`

## Installation

### 1) Lancer Ganache
Par défaut l'app vise :
- RPC : `http://127.0.0.1:7545`
- Backend : `http://127.0.0.1:2020`

### 2) Installer les dépendances Python
```bash
cd guess_number_dapp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Démarrer le backend
```bash
python backend.py
```

Au premier lancement, `py-solc-x` peut installer le compilateur Solidity `0.8.20`.

### 4) Ouvrir le frontend
Ouvre simplement `frontend/index.html` dans ton navigateur.

## Utilisation

## Paramètres globaux
Dans le panneau **Paramètres** :
- colle la **clé privée du joueur A**
- colle la **clé privée du joueur B**
- optionnel : force une **adresse de joueur B** si tu veux une adresse différente de celle dérivée de la clé privée

Le frontend appelle le backend pour :
- récupérer les adresses et balances
- déployer les contrats
- envoyer les transactions
- lire l'état des contrats

## Version 1
- A déploie avec son secret et le nombre max d'essais
- B envoie ses guesses
- le contrat retourne `plus petit`, `plus grand` ou `correct`

## Version 2
- A déploie avec une mise en ETH
- B rejoint avec exactement la même mise
- si B trouve le bon nombre, il gagne le pot
- sinon A récupère le pot quand le nombre d'essais est épuisé

## Version 3
- déploie d'abord **un seul contrat générique**
- A crée une partie dans ce contrat
- B rejoint cette partie
- B joue sur `gameId`
- tu peux lister toutes les parties

## Version 4
Cette version est la plus délicate.

### Ce qui est implémenté ici
On utilise une **approche pratique de confidentialité** :
- A choisit un secret
- le backend construit localement un **arbre de Merkle** de toutes les réponses possibles pour les guesses `1..100`
- seul le **Merkle root** part on-chain
- B soumet un guess
- A résout ce guess avec une **preuve Merkle**
- le contrat vérifie la preuve sans jamais stocker le secret sur la blockchain

### Pourquoi cette approche
Sur Ethereum public, faire une vraie comparaison privée on-chain sans révéler le secret demande des mécanismes plus lourds, typiquement **ZK proofs** ou autre design cryptographique avancé.

Là, tu as une version :
- fonctionnelle
- vérifiable on-chain
- sans secret stocké en clair
- beaucoup plus réaliste pour un projet pédagogique

## API backend
Principales routes :

### Général
- `POST /account/info`
- `GET /health`

### V1
- `POST /v1/deploy`
- `POST /v1/state`
- `POST /v1/guess`

### V2
- `POST /v2/deploy`
- `POST /v2/state`
- `POST /v2/join`
- `POST /v2/guess`

### V3
- `POST /v3/deploy`
- `POST /v3/create_game`
- `POST /v3/list_games`
- `POST /v3/state`
- `POST /v3/join_game`
- `POST /v3/guess`

### V4
- `POST /v4/prepare`
- `POST /v4/deploy`
- `POST /v4/state`
- `POST /v4/join`
- `POST /v4/submit_guess`
- `POST /v4/resolve_guess`

## Notes utiles
- Le frontend est volontairement simple pour limiter les bugs.
- Tout passe par le backend Python, donc pas besoin de MetaMask.
- C'est pensé pour **Ganache local**, pas pour de la prod.
- Si Ganache redémarre, les nonces / adresses / balances peuvent changer selon la config.
