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
    players.setdefault(ctx.author.id, []).append({
        "puuid": res["puuid"],
        "name": pseudo
    })
    await ctx.send(f"Riot ID {pseudo} enregistré avec succès.")

@tasks.loop(seconds=10)
async def check_games():
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

async def send_game_end(channel, pseudo_riot, gamemode, champ_name, champ_slug, result, kda, match_id):
    champ_icon_url = f"http://ddragon.leagueoflegends.com/cdn/13.6.1/img/champion/{champ_slug}.png"

    embed = discord.Embed(
        title="Victoire" if result == "gagné" else "Défaite",
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

bot.run(TOKEN_DISCORD)
