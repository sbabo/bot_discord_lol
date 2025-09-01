"""
Bot Discord pour tracker les parties League of Legends
======================================================

Ce bot surveille les parties en cours des joueurs enregistrés et envoie des notifications
sur Discord quand ils commencent ou terminent une partie.

Fonctionnalités:
- Enregistrement de comptes Riot Games via la commande !register
- Surveillance automatique des parties en cours
- Notifications avec embeds stylisés pour début/fin de partie
- Liens vers Porofessor (parties en cours) et LeagueOfGraphs (parties terminées)
- Support de plusieurs comptes par utilisateur Discord

Auteur: sbabo
Repository: https://github.com/sbabo/bot_discord_lol
"""

import discord
from discord.ext import commands, tasks # type: ignore
import requests
import asyncio
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Configuration Flask pour keep-alive (déploiement)
app = Flask("keep_alive")

@app.route("/")
def home():
    """Endpoint de santé pour vérifier que le bot fonctionne."""
    return "Bot is running..."

def run_flask():
    """Démarre le serveur Flask en arrière-plan."""
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    """Maintient le bot en vie en démarrant un serveur Flask."""
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
print("Démarrage du bot...")

# Chargement des variables d'environnement
load_dotenv()

TOKEN_DISCORD = os.getenv("TOKEN_DISCORD")
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Configuration des intents Discord
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionnaires de stockage des données
players = {}  # {discord_id: [{"puuid": str, "name": str}, ...]}
active_games = {}  # {(puuid, match_id): True}

# Cache des champions League of Legends
champs_by_id = {}  # {champion_id: {"slug": str, "name": str}}

def load_champ_mapping():
    """
    Charge la correspondance ID champion -> nom/slug depuis l'API Data Dragon.
    
    Cette fonction récupère les données des champions depuis l'API officielle
    de Riot Games et crée un mapping pour convertir les IDs de champions
    en noms lisibles et slugs pour les URLs d'icônes.
    """
    global champs_by_id
    try:
        dd_url = "http://ddragon.leagueoflegends.com/cdn/13.6.1/data/en_US/champion.json"
        data = requests.get(dd_url, timeout=10).json()
        mapping = {}
        for _, value in data["data"].items():
            mapping[int(value["key"])] = {"slug": value["id"], "name": value["name"]}
        champs_by_id = mapping
        print("Champions chargés avec succès.")
    except Exception as e:
        print(f"Erreur lors du chargement des champions : {e}")
        champs_by_id = {}

def champ_from_id(champ_id):
    """
    Convertit un ID de champion en slug et nom lisible.
    
    Args:
        champ_id: ID du champion (int ou str)
        
    Returns:
        tuple: (slug, nom_lisible) pour le champion
        
    Example:
        >>> champ_from_id(222)
        ('Jinx', 'Jinx')
    """
    try:
        champ_id = int(champ_id)  # conversion systématique
    except Exception:
        return str(champ_id), f"Champion {champ_id}"

    champion = champs_by_id.get(champ_id)
    if champion:
        print(f"Champion trouvé : {champion['name']}")
        return champion["slug"], champion["name"]
    else:
        print(f"Aucun mapping pour {champ_id}")
    return str(champ_id), f"Champion {champ_id}"

def riot_access(url):
    """
    Effectue une requête HTTP vers l'API Riot Games.
    
    Args:
        url (str): URL de l'endpoint API à interroger
        
    Returns:
        requests.Response: Objet réponse de la requête
    """
    headers = {
        "X-Riot-Token": RIOT_API_KEY
    }
    r = requests.get(url, headers=headers)
    return r

@bot.event            
async def on_ready():
    """Événement déclenché quand le bot est prêt."""
    print(f"{bot.user} est connecté !")
    load_champ_mapping()
    # await test_last_match("OKj8ktwdPr5t4v0HGnMnq7TdfjON_vhd7rUss2WFYxVd_axHL71FGAyKStwO8mbf3NaDB0Dcy0e5GA", "SavvyStory#EUW")
    check_games.start()

@bot.command(name="ping")
async def ping(ctx):
    """Commande de test pour vérifier que le bot répond."""
    await ctx.send("Pong!")

@bot.command(name="register")
async def register(ctx, *, pseudo: str):
    """
    Enregistre un compte Riot Games pour surveillance.
    
    Args:
        pseudo (str): Pseudo au format "Nom#TAG" (ex: "Player#EUW")
        
    Usage:
        !register Player#EUW
    """
    if "#" not in pseudo:
        await ctx.send("Format invalide : Nom#TAG")
        return
    name, tag = pseudo.split("#")
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    res = riot_access(url).json()
    if "puuid" not in res:
        await ctx.send("Riot ID invalide.")
        return
    players.setdefault(ctx.author.id, []).append({
        "puuid": res["puuid"],
        "name": pseudo
    })
    await ctx.send(f"Riot ID {pseudo} enregistré avec succès.")

@tasks.loop(seconds=10)
async def check_games():
    """
    Boucle principale qui vérifie périodiquement l'état des parties.
    
    Cette fonction s'exécute toutes les 10 secondes et :
    - Vérifie si les joueurs enregistrés sont en partie
    - Envoie des notifications quand une partie commence
    - Détecte la fin des parties et affiche les résultats
    """
    channel = (bot.get_channel(int(CHANNEL_ID)) or await bot.fetch_channel(int(CHANNEL_ID)))

    for discord_id, infos in players.items():
        for info in infos:  # infos est une liste de comptes
            puuid = info["puuid"]
            pseudo_riot = info["name"]

            # Vérifier si le joueur est en partie
            spectate_url = f"https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
            game_resp = riot_access(spectate_url)

            if game_resp.status_code == 200:
                data = game_resp.json()
                match_id = str(data["gameId"])
                queue_id = str(data.get("gameQueueConfigId", -1))

                gamemode = {
                    "420": "Classé Solo/Duo",
                    "440": "Classé Flex",
                    "400": "Normal Draft",
                    "3100": "Custom"
                }.get(queue_id, f"Queue {queue_id}")

                # Trouver le champion joué
                champ_id = None
                for p in data.get("participants", []):
                    if p.get("puuid") == puuid:
                        champ_id = p.get("championId", 0)
                        break

                champ_slug, champ_name = champ_from_id(champ_id)

                # Si nouvelle partie pour ce joueur
                if (puuid, match_id) not in active_games:
                    active_games[(puuid, match_id)] = True
                    await send_game_start(channel, pseudo_riot, gamemode, champ_name, champ_slug, match_id)

            else:
                # Si le joueur avait une partie en cours mais n'est plus en jeu
                for (p, m) in list(active_games.keys()):
                    if p == puuid:
                        match_id = m  # Définit la variable pour éviter UnboundLocalError
                        # Récupérer le dernier match
                        last_match_url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=1"
                        last_match = riot_access(last_match_url).json()
                        if not last_match:
                            del active_games[(p, m)]
                            continue

                        details_url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{last_match[0]}"
                        details = riot_access(details_url).json()

                        # Chercher le joueur dans les participants
                        for part in details["info"]["participants"]:
                            if part["puuid"] == puuid:
                                kda = f"{part['kills']}/{part['deaths']}/{part['assists']}"
                                champ_slug, champ_name = champ_from_id(part["championId"])
                                win = part["win"]
                                queue = details["info"].get("queueId", -1)
                                gamemode = {
                                    420: "Classé Solo/Duo",
                                    440: "Classé Flex",
                                    400: "Normal Draft",
                                    3100: "Custom"
                                }.get(queue, f"Queue {queue}")

                                await send_game_end(channel, pseudo_riot, gamemode, champ_name, champ_slug, win, kda, last_match[0])
                                break

                        # Supprimer la partie active
                        del active_games[(p, m)]

async def send_game_start(channel, pseudo_riot, gamemode, champ_name, champ_slug, match_id):
    """
    Envoie un embed Discord notifiant qu'une partie vient de commencer.
    
    Args:
        channel: Channel Discord où envoyer le message
        pseudo_riot (str): Pseudo Riot du joueur (format "Nom#TAG")
        gamemode (str): Mode de jeu (ex: "Classé Solo/Duo")
        champ_name (str): Nom du champion joué
        champ_slug (str): Slug du champion pour l'URL de l'icône
        match_id (str): ID de la partie
    """
    pseudo_formatted = pseudo_riot.replace("#", "-")
    champ_icon_url = f"http://ddragon.leagueoflegends.com/cdn/13.6.1/img/champion/{champ_slug}.png"

    embed = discord.Embed(
        title="Partie en cours",
        url=f"https://porofessor.gg/fr/live/euw/{pseudo_formatted}",
        description=f"{pseudo_riot} est en partie {gamemode} !",
        color=discord.Color.blue()
    )
    embed.add_field(name="Mode", value=gamemode)
    embed.add_field(name="Champion", value=champ_name, inline=True)

    embed.set_thumbnail(url=champ_icon_url)
    
    embed.set_footer(text=f"Match ID: {match_id}")
    await channel.send(embed=embed)

async def send_game_end(channel, pseudo_riot, gamemode, champ_name, champ_slug, result, kda, match_id):
    """
    Envoie un embed Discord avec les résultats d'une partie terminée.
    
    Args:
        channel: Channel Discord où envoyer le message
        pseudo_riot (str): Pseudo Riot du joueur
        gamemode (str): Mode de jeu
        champ_name (str): Nom du champion joué
        champ_slug (str): Slug du champion pour l'URL de l'icône
        result (bool): True si victoire, False si défaite
        kda (str): Score KDA au format "kills/deaths/assists"
        match_id (str): ID de la partie pour le lien LeagueOfGraphs
    """
    champ_icon_url = f"http://ddragon.leagueoflegends.com/cdn/13.6.1/img/champion/{champ_slug}.png"

    embed = discord.Embed(
        title="Victoire" if result == "gagné" else "Défaite",
        url=f"https://www.leagueofgraphs.com/fr/match/euw/{match_id}",
        description=f"{pseudo_riot} a terminé sa partie {gamemode} !",
        color=discord.Color.green() if result == "gagné" else discord.Color.red(),
    )
    embed.add_field(name="Mode", value=gamemode)
    embed.add_field(name="Champion", value=champ_name, inline=True)
    embed.add_field(name="Résultat", value="Victoire" if result == "gagné" else "Défaite", inline=True)
    embed.add_field(name="KDA", value=kda, inline=True)

    embed.set_thumbnail(url=champ_icon_url)
    embed.set_footer(text=f"Match ID: {match_id}")

    await channel.send(embed=embed)
    
    
def update_lp(pseudo, puuid):
    """Met à jour les LP et le delta quotidien pour un joueur"""
    url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/{puuid}"
    data = riot_access(url).json()
    
    #On recherche la file classé Solo/Duo
    for entry in data:
        if entry["queueType"] == "RANKED_SOLO_5x5":
            # On pourrait stocker les LP et le delta ici
            new_lp = entry["leaguePoints"]
            tier = entry["tier"]
            rank = entry["rank"]
            
            old_lp = players[pseudo].get("lp", new_lp)
            diff = new_lp - old_lp
            players[pseudo]["lp"] = new_lp
            players[pseudo]["tier"] = tier
            players[pseudo]["rank"] = rank
            players[pseudo]["daily_lp"] = players[pseudo].get("daily_lp", 0) + diff
            print(f"{pseudo} - LP mis à jour: {new_lp} ({'+' if diff > 0 else ''}{diff})")
            break

@bot.command(name="leaderboard")
async def leaderboard(channel):
    if not players:
        await channel.send("Aucun joueur enregistré.")
        return
    
    sorted_players = sorted(
        players.values(),
        key=lambda x: (x.get("tier", ""), x.get("rank", ""), x.get("lp", 0)),
        reverse=True
    )
    """
    Affiche le classement des joueurs enregistrés par LP.
    
    Cette fonction récupère le rang de chaque joueur via l'API Riot Games
    et affiche un classement trié par points de ligue (LP).
    """
    
    embed = discord.Embed(
        title="Classement des joueurs",
        color=discord.Color.gold())
    
    for i, p in enumerate(sorted_players, start=1):
        lp = p.get("lp", 0)
        tier = p.get("tier", "?")
        rank = p.get("rank", "?")
        embed.add_field(
            name=f"{i}. {p['name']}",
            value=f"{tier} {rank} - {lp} LP",
            inline=False
        )

    await channel.send(embed=embed)

keep_alive()
bot.run(TOKEN_DISCORD)
