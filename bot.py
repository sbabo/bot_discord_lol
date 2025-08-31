import discord
from discord.ext import commands, tasks # type: ignore
import requests
import asyncio
import os
from dotenv import load_dotenv

print("Démarrage du bot...")

load_dotenv()

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

champs_by_id = {}

def load_champ_mapping():
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
    headers = {
        "X-Riot-Token": RIOT_API_KEY
    }
    r = requests.get(url, headers=headers)
    return r

@bot.event            
async def on_ready():
    print(f"{bot.user} est connecté !")
    load_champ_mapping()
    # await test_last_match("OKj8ktwdPr5t4v0HGnMnq7TdfjON_vhd7rUss2WFYxVd_axHL71FGAyKStwO8mbf3NaDB0Dcy0e5GA", "SavvyStory#EUW")
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
        
        champ = None

        channel = (bot.get_channel(int(CHANNEL_ID)) or await bot.fetch_channel(int(CHANNEL_ID)))

        print(f"Vérification du joueur {discord_id}...")
        
        # On vérifie le retour de l'API
        if game.status_code == 200:
            print(f"Le joueur {discord_id} est en partie.")
            data = game.json()
            queue_id = str(data["gameQueueConfigId"])
            print(f"Queue ID: {queue_id}")
            
            # On vérifie le type de la partie
            if queue_id in ["3100", "420", "440", "400"]:
                print(f"Le joueur {discord_id} est en SoloQ ou Flex.")
                gamemode = "SoloQ" if queue_id == "420" else "Flex" if queue_id == "440" else "Normal/Custom"
                match_id = str(data["gameId"])

                for p in data['participants']:
                    print(p)
                    if p['puuid'] == puuid:
                        champ = p['championId']
                        break

                # Si une nouvelle partie est détectée
                if discord_id not in active_games or active_games[discord_id] != match_id:
                    print(f"Nouvelle partie détectée pour le joueur {discord_id}.")
                    active_games[discord_id] = match_id
                    await send_game_start(channel, pseudo_riot, gamemode, champ, match_id)
        else:
            # Si le joueur n'est plus en partie
            if discord_id in active_games:
                last_match_url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
                last_match = riot_access(last_match_url).json()
                details_url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{last_match[0]}"
                details = riot_access(details_url).json()

                # Recherche des stats du joueurs
                for p in details["info"]["participants"]:
                    if p["puuid"] == puuid:
                        kda = f"{p['kills']}/{p['deaths']}/{p['assists']}"
                        champ = p["championId"]
                        result = "Victoire" if p["win"] else "Défaite"
                        queue = details["info"]["queueId"]
                        gamemode = "SoloQ" if queue == 420 else "Flex" if queue == 440 else "Normal/Custom"
                        await send_game_end(channel, pseudo_riot, gamemode, champ, result, kda, last_match[0])
                        break
                del active_games[discord_id]

async def send_game_start(channel, pseudo_riot, gamemode, champion, match_id):
    champ_slug, champ_name = champ_from_id(champion)
    champ_icon_url = f"http://ddragon.leagueoflegends.com/cdn/13.6.1/img/champion/{champ_slug}.png"

    embed = discord.Embed(
        title="Partie en cours",
        description=f"{pseudo_riot} est en partie {gamemode} !",
        color=discord.Color.blue()
    )
    embed.add_field(name="Mode", value=gamemode)
    embed.add_field(name="Champion", value=champ_name, inline=True)

    embed.set_thumbnail(url=champ_icon_url)
    
    embed.set_footer(text=f"Match ID: {match_id}")
    await channel.send(embed=embed)

async def send_game_end(channel, pseudo_riot, gamemode, champion_id, result, kda, match_id):
    champ_slug, champ_name = champ_from_id(champion_id)
    champ_icon_url = f"http://ddragon.leagueoflegends.com/cdn/13.6.1/img/champion/{champ_slug}.png"

    embed = discord.Embed(
        title="Victoire" if result == "gagné" else "Défaite",
        description=f"{pseudo_riot} a terminé sa partie {gamemode} !",
        color=discord.Color.green() if result == "gagné" else discord.Color.red(),
    )
    embed.add_field(name="Mode", value=gamemode)
    embed.add_field(name="Champion", value=champ_name, inline=True)
    embed.add_field(name="Résultat", value=result, inline=True)
    embed.add_field(name="KDA", value=kda, inline=True)

    embed.set_thumbnail(url=champ_icon_url)
    embed.set_footer(text=f"Match ID: {match_id}")

    await channel.send(embed=embed)

bot.run(TOKEN_DISCORD)
