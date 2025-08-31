import discord
from discord.ext import commands, tasks # type: ignore
import requests
import asyncio
import os

print("Démarrage du bot...")


TOKEN_DISCORD = os.getenv("TOKEN_DISCORD")
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

players = {}
active_games = {}

def riot_access(url):
    headers = {
        "X-Riot-Token": RIOT_API_KEY
    }
    r = requests.get(url, headers=headers)
    return r

@bot.event            
async def on_ready():
    print(f"{bot.user} est connecté !")
    check_games.start()

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command(name="register")
async def register(ctx, *, pseudo: str):
    if "#" not in pseudo:
        await ctx.send("Format invalide : Nom#TAG")
        return
    name, tag = pseudo.split("#")
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    res = riot_access(url).json()
    if "puuid" not in res:
        await ctx.send("Riot ID invalide.")
        return
    players[ctx.author.id] = {"puuid": res["puuid"], "name": pseudo}
    await ctx.send(f"Riot ID {pseudo} enregistré avec succès.")
    
@tasks.loop(seconds=10)
async def check_games():
    
    print(players)
    for discord_id, info in players.items():
        
        info = players[discord_id]
        pseudo_riot =info["name"]
        puuid = info["puuid"]

        spectate_url = f"https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        game = riot_access(spectate_url)

        channel = (bot.get_channel(int(CHANNEL_ID)) or await bot.fetch_channel(int(CHANNEL_ID)))

        print(f"Vérification du joueur {discord_id}...")
        
        # On vérifie le retour de l'API
        if game.status_code == 200:
            print(f"Le joueur {discord_id} est en partie.")
            data = game.json()
            queue_id = str(data["gameQueueConfigId"])
            print(f"Queue ID: {queue_id}")
            # On vérifie que qu'il s'agit d'une SoloQ ou d'une Flex(440)
            if queue_id in ["3100", "420", "440"]:
                print(f"Le joueur {discord_id} est en SoloQ ou Flex.")
                match_id = str(data["gameId"])
                
                # Si une nouvelle partie est détectée
                if discord_id not in active_games or active_games[discord_id] != match_id:
                    print(f"Nouvelle partie détectée pour le joueur {discord_id}.")
                    active_games[discord_id] = match_id
                    await channel.send(f"{pseudo_riot} est en partie {match_id} !")
        else:
            # Si le joueur n'est plus en partie
            if discord_id in active_games:
                last_match_url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
                last_match = riot_access(last_match_url)
                details_url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{last_match[0]}"
                details = riot_access(details_url)
                
                # Recherche des stats du joueurs
                for p in details["info"]["participants"]:
                    if p["puuid"] == puuid:
                        kda = f"{p['kills']}/{p['deaths']}/{p['assists']}"
                        champ = p["championName"]
                        win = "gagné" if p["win"] else "perdu"
                        queue = details["info"]["queueId"]
                        gamemode = "SoloQ" if queue == 420 else "Flex" if queue == 440 else "Autre"
                        await channel.send(f"{pseudo_riot} a fini sa partie {gamemode} avec **{champ}** : {win} - KDA: {kda} !")
                        break
                del active_games[discord_id]

bot.run(TOKEN_DISCORD)
