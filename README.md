# Bot Discord League of Legends Tracker

Un bot Discord qui surveille automatiquement les parties League of Legends de vos joueurs favoris et envoie des notifications stylisées avec des informations détaillées.

![Discord](https://img.shields.io/badge/Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![League of Legends](https://img.shields.io/badge/League%20of%20Legends-C89B3C?style=for-the-badge&logo=riot-games&logoColor=white)

## 🚀 Fonctionnalités

### 📊 Surveillance en temps réel
- **Détection automatique** des parties en cours
- **Notifications instantanées** quand une partie commence ou se termine
- **Support multi-comptes** : plusieurs comptes Riot par utilisateur Discord

### 🎮 Informations détaillées
- **Champion joué** avec icône officielle
- **Mode de jeu** (Classé Solo/Duo, Flex, Normal Draft, etc.)
- **Résultats complets** : Victoire/Défaite, KDA, Match ID
- **Liens directs** vers Porofessor (parties en cours) et LeagueOfGraphs (historique)

### 🏆 Système de classement
- **Leaderboard** des joueurs enregistrés
- **Tri par LP** (Points de Ligue)
- **Affichage du rang** et division

## 📦 Installation

### Prérequis
- Python 3.8 ou supérieur
- Un bot Discord configuré
- Une clé API Riot Games

### 1. Cloner le repository
```bash
git clone https://github.com/sbabo/bot_discord_lol.git
cd bot_discord_lol
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Configuration
Créez un fichier `.env` à la racine du projet :
```env
TOKEN_DISCORD=votre_token_discord_bot
RIOT_API_KEY=votre_cle_api_riot
CHANNEL_ID=id_du_channel_discord
```

### 4. Lancer le bot
```bash
python bot.py
```

## 🔧 Configuration

### Obtenir un token Discord
1. Allez sur le [Discord Developer Portal](https://discord.com/developers/applications)
2. Créez une nouvelle application
3. Dans la section "Bot", copiez le token

### Obtenir une clé API Riot Games
1. Rendez-vous sur le [Riot Developer Portal](https://developer.riotgames.com/)
2. Connectez-vous avec votre compte Riot
3. Créez une nouvelle clé API

### Permissions Discord requises
- `Send Messages`
- `Embed Links`
- `Read Message History`
- `Use Slash Commands`

## 🎯 Utilisation

### Commandes disponibles

| Commande | Description | Exemple |
|----------|-------------|---------|
| `!ping` | Test de connexion | `!ping` |
| `!register` | Enregistrer un compte Riot | `!register Player#EUW` |
| `!leaderboard` | Afficher le classement | `!leaderboard` |

### Notifications automatiques

#### 🟢 Partie en cours
- Notification instantanée quand un joueur entre en partie
- Lien vers Porofessor pour l'analyse en temps réel
- Affichage du champion et du mode de jeu

#### 🔴 Fin de partie
- Résultats détaillés (Victoire/Défaite)
- Score KDA complet
- Lien vers LeagueOfGraphs pour l'analyse post-game

## 🏗️ Architecture

```
bot.py                 # Fichier principal du bot
├── Configuration      # Variables d'environnement
├── API Riot Games     # Intégration avec l'API officielle
├── Data Dragon        # Récupération des données champions
├── Discord Bot        # Commandes et événements
└── Flask Server       # Keep-alive pour le déploiement
```

### Structures de données
- `players`: Stockage des comptes enregistrés par utilisateur Discord
- `active_games`: Suivi des parties en cours
- `champs_by_id`: Cache des informations champions

## 🌐 APIs utilisées

- **Riot Games API** : Données de jeu en temps réel
- **Data Dragon** : Informations sur les champions
- **Discord API** : Intégration bot Discord

## 🚀 Déploiement

### Déploiement local
```bash
python bot.py
```

### Déploiement sur serveur
Le bot inclut un serveur Flask pour les services de déploiement :
- Port : 8080
- Endpoint de santé : `/`

### Variables d'environnement
```env
TOKEN_DISCORD=        # Token du bot Discord
RIOT_API_KEY=         # Clé API Riot Games
CHANNEL_ID=           # ID du channel Discord pour les notifications
```

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer :

1. **Fork** le projet
2. **Créez** votre branche feature (`git checkout -b feature/AmazingFeature`)
3. **Committez** vos changements (`git commit -m 'Add some AmazingFeature'`)
4. **Push** vers la branche (`git push origin feature/AmazingFeature`)
5. **Ouvrez** une Pull Request

## 📝 Changelog

### Version actuelle
- ✅ Surveillance automatique des parties
- ✅ Notifications avec embeds stylisés
- ✅ Support multi-comptes
- ✅ Intégration Porofessor/LeagueOfGraphs
- ✅ Système de classement
- ✅ Documentation complète

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🐛 Signaler un bug

Si vous trouvez un bug, veuillez :
1. Vérifier qu'il n'existe pas déjà dans les [Issues](https://github.com/sbabo/bot_discord_lol/issues)
2. Créer une nouvelle issue avec :
   - Description détaillée du problème
   - Étapes pour reproduire
   - Screenshots si pertinent

## 📞 Support

- 🐛 Issues : [GitHub Issues](https://github.com/sbabo/bot_discord_lol/issues)

---

Made with ❤️ by [sbabo](https://github.com/sbabo)
