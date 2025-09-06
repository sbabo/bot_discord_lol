"""
Bot Discord pour tracker les parties League of Legends
======================================================

Ce bot minimaliste surveille les comptes Riot Games enregistrés et génère
des résumés quotidiens automatiques des performances en ranked.

Fonctionnalités principales:
- Enregistrement de comptes Riot Games via !register
- Système de persistence des données (JSON)
- Résumé quotidien automatique à 9h (SoloQ + FlexQ)
- Classement des joueurs via !leaderboard
- Suivi des LP et statistiques journalières

Architecture:
- bot.py: Bot Discord principal avec commandes et tâches programmées
- persistence.py: Module de gestion des données (sauvegarde/chargement JSON)
- bot_data.json: Fichier de persistence des joueurs et statistiques

Auteur: sbabo
Repository: https://github.com/sbabo/bot_discord_lol
Branche: persistence
"""

import discord
from discord.ext import commands, tasks
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from persistence import load_data, save_data, add_player, update_player
from threading import Thread
from flask import Flask
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# =============================================================================
# CONFIGURATION ET CONSTANTES
# =============================================================================

# Configuration du résumé quotidien
SCHEDULE_HOUR = 9        # Heure d'envoi du résumé quotidien
SCHEDULE_MINUTE = 0      # Minute d'envoi du résumé quotidien  
TIMEZONE = ZoneInfo("Europe/Paris")  # Timezone pour le scheduling

# Chargement des variables d'environnement depuis .env
load_dotenv()
TOKEN_DISCORD = os.getenv("TOKEN_DISCORD")    # Token du bot Discord
RIOT_API_KEY = os.getenv("RIOT_API_KEY")      # Clé API Riot Games
CHANNEL_ID = os.getenv("CHANNEL_ID")          # ID du channel Discord

# Configuration du bot Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# =============================================================================
# VARIABLES GLOBALES
# =============================================================================

# Chargement des données persistées depuis JSON
players = load_data()           # Liste des joueurs enregistrés
active_games = {}               # Cache des parties en cours (pour suivi temps réel)
champs_by_id = {}              # Cache des champions League of Legends

# Ordre hiérarchique des ranks pour le classement
rank_order = {
    "IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4,
    "PLATINUM": 5, "DIAMOND": 6, "MASTER": 7,
    "GRANDMASTER": 8, "CHALLENGER": 9, "UNRANKED": 99
}

# Ordre hiérarchique des divisions pour le classement
division_order = {"IV": 4, "III": 3, "II": 2, "I": 1, "": 99}

# Variable pour éviter les doublons de résumé quotidien
last_daily_date = None

# =============================================================================
# FLASK SERVER (KEEP-ALIVE POUR DÉPLOIEMENT)
# =============================================================================

app = Flask("keep_alive")

@app.route("/")
def home():
    """Endpoint de santé pour vérifier que le bot fonctionne."""
    return "Bot is running..."

def run_flask():
    """Démarre le serveur Flask en arrière-plan."""
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    """
    Maintient le bot en vie en démarrant un serveur Flask.
    Utile pour les services de déploiement gratuits (Replit, Heroku, etc.)
    """
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# =============================================================================
# API RIOT GAMES - FONCTIONS UTILITAIRES
# =============================================================================

def riot_access(url):
    """
    Effectue une requête HTTP vers l'API Riot Games.
    
    Args:
        url (str): URL de l'endpoint API à interroger
        
    Returns:
        requests.Response: Objet réponse de la requête
    """
    headers = {"X-Riot-Token": RIOT_API_KEY}
    return requests.get(url, headers=headers)

def load_champ_mapping():
    """
    Charge la correspondance ID champion -> nom/slug depuis l'API Data Dragon.
    
    Cette fonction récupère les données des champions depuis l'API officielle
    de Riot Games et crée un mapping pour convertir les IDs de champions
    en noms lisibles et slugs pour les URLs d'icônes.
    """
    global champs_by_id
    dd_url = "http://ddragon.leagueoflegends.com/cdn/13.6.1/data/en_US/champion.json"
    data = requests.get(dd_url).json()
    champs_by_id = {int(v["key"]): {"slug": v["id"], "name": v["name"]} for v in data["data"].values()}

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
        champ_id = int(champ_id)
        champ = champs_by_id.get(champ_id)
        return (champ["slug"], champ["name"]) if champ else (str(champ_id), f"Champion {champ_id}")
    except:
        return str(champ_id), f"Champion {champ_id}"

# =============================================================================
# SYSTÈME DE SUIVI DES LP (LEAGUE POINTS)
# =============================================================================

def update_lp(pseudo, puuid):
    """
    Met à jour les LP et le delta quotidien pour SoloQ et FlexQ d'un joueur.
    
    Cette fonction interroge l'API Riot pour récupérer les informations
    de classement actuelles et calcule automatiquement les variations
    de LP par rapport aux valeurs précédentes.
    
    Args:
        pseudo (str): Pseudo Riot du joueur (format "Nom#TAG")
        puuid (str): PUUID unique du joueur Riot
    """
    url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    data = riot_access(url).json()
    
    # Cherche le compte dans la liste players
    target = None
    for p in players:
        if p["puuid"] == puuid:
            target = p
            break
    if not target:
        return
        
    # Initialise les structures de données si absentes
    target["solo"] = {"tier": "UNRANKED","rank":"","lp":0,"daily_lp":0}
    target["flex"] = {"tier": "UNRANKED","rank":"","lp":0,"daily_lp":0}
    
    if not data: 
        return
        
    # Met à jour les informations pour chaque queue
    for entry in data:
        q, lp, tier, rank = entry["queueType"], entry["leaguePoints"], entry["tier"], entry["rank"]
        
        if q=="RANKED_SOLO_5x5":
            diff = lp - target["solo"].get("lp", lp)
            target["solo"].update({"tier":tier,"rank":rank,"lp":lp,"daily_lp":target["solo"].get("daily_lp",0)+diff})
        elif q=="RANKED_FLEX_SR":
            diff = lp - target["flex"].get("lp", lp)
            target["flex"].update({"tier":tier,"rank":rank,"lp":lp,"daily_lp":target["flex"].get("daily_lp",0)+diff})
    
    # Sauvegarde automatique des données mises à jour        
    save_data(players)

# =============================================================================
# COMMANDES DISCORD
# =============================================================================

@bot.command(name="register")
async def register(ctx, *, pseudo: str):
    """
    Enregistre un compte Riot Games pour surveillance.
    
    Cette commande permet d'ajouter un compte Riot à la liste des joueurs
    surveillés par le bot. Une fois enregistré, le joueur apparaîtra dans
    les résumés quotidiens et les classements.
    
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
        
    account = {"puuid": res["puuid"], "name": pseudo}
    
    if add_player(account, players):
        update_lp(account["name"], account["puuid"])
        await ctx.send(f"Riot ID {pseudo} enregistré avec succès.")
    else:
        await ctx.send(f"Le compte {pseudo} est déjà enregistré.")

@bot.command(name="leaderboard")
async def leaderboard_cmd(ctx):
    """
    Affiche le classement des joueurs enregistrés en SoloQ.
    
    Cette commande génère un embed Discord avec le classement de tous
    les joueurs enregistrés, triés par tier, division et LP.
    """
    if not players:
        await ctx.send("Aucun joueur enregistré.")
        return
        
    # Préparation des données de classement
    leaderboard_players = []
    for p in players:
        s = p.get("solo", {"tier":"UNRANKED","rank":"","lp":0})
        leaderboard_players.append({
            "name": p["name"], 
            "tier": s["tier"], 
            "rank": s["rank"], 
            "lp": s["lp"]
        })
    
    # Tri par ordre hiérarchique (tier > division > LP)
    sorted_players = sorted(
        leaderboard_players,
        key=lambda x: (
            rank_order.get(x["tier"],0), 
            division_order.get(x["rank"],0), 
            -x["lp"] if x["tier"]!="UNRANKED" else 0
        )
    )
    
    # Génération de l'embed
    embed = discord.Embed(title="Classement SoloQ", color=discord.Color.gold())
    for i, p in enumerate(sorted_players, 1):
        embed.add_field(
            name=f"{i}. {p['name']}", 
            value=f"{p['tier']} {p['rank']} - {p['lp']} LP", 
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    """Commande de test pour vérifier que le bot répond."""
    await ctx.send("Pong!")

# =============================================================================
# RÉSUMÉ QUOTIDIEN AUTOMATIQUE
# =============================================================================

async def send_daily_summary(channel, summary_date):
    """
    Envoie le résumé quotidien des performances de tous les joueurs.
    
    Cette fonction génère deux embeds Discord (SoloQ et FlexQ) avec les
    statistiques de la veille : tier, rank, LP actuels, delta quotidien,
    nombre de victoires/défaites et winrate.
    
    Args:
        channel: Channel Discord où envoyer le résumé
        summary_date (datetime): Date de référence pour le résumé
    """
    yesterday = (summary_date - timedelta(days=1)).date()
    
    # Création des embeds pour chaque queue
    embed_solo = discord.Embed(
        title=f"📊 Résumé SoloQ du {yesterday}", 
        color=discord.Color.blue()
    )
    embed_flex = discord.Embed(
        title=f"📊 Résumé FlexQ du {yesterday}", 
        color=discord.Color.green()
    )
    
    # Génération des statistiques pour chaque joueur
    for acc in players:
        name = acc.get("name","Unknown#TAG")
        
        for queue, embed in [("solo", embed_solo), ("flex", embed_flex)]:
            q = acc.get(queue,{})
            tier, rank, lp = q.get("tier","UNRANKED"), q.get("rank",""), q.get("lp",0)
            delta = q.get("daily_lp",0)
            wins, losses = q.get("wins",0), q.get("losses",0)
            total = wins + losses
            winrate = f"{(wins/total*100):.1f}%" if total>0 else "0%"
            
            value = f"{tier} {rank} - {lp} LP (Δ {delta:+})\n" \
                   f"Victoires: {wins} - Défaites: {losses} ({winrate})"
            
            embed.add_field(name=name, value=value, inline=False)
            
            # Reset du delta quotidien après affichage
            q["daily_lp"] = 0
    
    # Envoi des embeds
    await channel.send(embed=embed_solo)
    await channel.send(embed=embed_flex)

# =============================================================================
# TÂCHES PROGRAMMÉES (BACKGROUND TASKS)
# =============================================================================

@tasks.loop(minutes=1)
async def daily_summary_scheduler():
    """
    Planificateur du résumé quotidien.
    
    Cette tâche s'exécute toutes les minutes et vérifie si l'heure
    programmée est atteinte (9h00 par défaut). Elle évite les doublons
    en gardant une trace de la dernière date d'envoi.
    
    Le résumé est envoyé une seule fois par jour à l'heure configurée.
    """
    global last_daily_date
    now = datetime.now(TIMEZONE)
    
    # Vérification de l'heure programmée
    if now.hour==SCHEDULE_HOUR and now.minute==SCHEDULE_MINUTE:
        today = now.date()
        
        # Éviter les doublons (si déjà envoyé aujourd'hui)
        if last_daily_date==today: 
            return
            
        # Récupération du channel et envoi du résumé
        channel = bot.get_channel(int(CHANNEL_ID)) or await bot.fetch_channel(int(CHANNEL_ID))
        await send_daily_summary(channel, now)
        last_daily_date = today

# =============================================================================
# ÉVÉNEMENTS DU BOT ET INITIALISATION
# =============================================================================

@bot.event
async def on_ready():
    """
    Événement déclenché quand le bot Discord est prêt et connecté.
    
    Cette fonction s'occupe de l'initialisation complète du bot :
    - Chargement du mapping des champions League of Legends
    - Démarrage du planificateur de résumé quotidien
    - Affichage des messages de confirmation
    """
    load_champ_mapping()
    print(f"{bot.user} est connecté !")
    
    # Démarrage du planificateur de résumé quotidien
    if not daily_summary_scheduler.is_running():
        daily_summary_scheduler.start()
    print("Daily summary scheduler démarré.")

# =============================================================================
# POINT D'ENTRÉE PRINCIPAL
# =============================================================================

# Démarrage du serveur Flask pour le keep-alive
keep_alive()

# Lancement du bot Discord
bot.run(TOKEN_DISCORD)