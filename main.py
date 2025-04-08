# Importation des modules nécessaires
from shutil import copy
from os import getenv, path
from dotenv import load_dotenv
from configparser import ConfigParser
from discord import Activity, ActivityType, Client, Intents
from openai import OpenAI

# Vérification de l’existence du fichier de configuration "settings.ini"
if not path.exists("settings.ini") and path.exists("settings.example.ini"):
    # Copie du fichier "settings.example.ini" vers "settings.ini"
    copy("settings.example.ini", "settings.ini")

# Chargement du fichier de configuration
config = ConfigParser()
config.read("settings.ini")

# Vérification que la section "SETTINGS" existe dans le fichier de configuration
if "SETTINGS" not in config:
    # Si la section "SETTINGS" n'existe pas, on la crée
    config["SETTINGS"] = {}

PROMPT = config["SETTINGS"].get("PROMPT", "")
MODEL = config["SETTINGS"].get("MODEL", "gemini-2.0-flash") or "gemini-2.0-flash"
CHANNELS = tuple(map(int, config["SETTINGS"]["CHANNELS"].split(","))) if "CHANNELS" in config["SETTINGS"] else (0,)
ACTIVITY_NAME = config["SETTINGS"].get("ACTIVITY_NAME", None)
activity_type = config["SETTINGS"].get("ACTIVITY_TYPE", None)
ACTIVITY_TYPE = getattr(ActivityType, activity_type, None) if activity_type else None
HISTORY_LENGTH = max(1, config["SETTINGS"].getint("HISTORY_LENGTH", 1))

# Si le fichier .env existe
if path.exists(".env"):
    # Chargement des variables d’environnement à partir du fichier .env
    load_dotenv()

# Récupération du jeton d’accès Discord à partir des variables d’environnement
DISCORD_TOKEN = getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    raise ValueError("Aucun jeton d’accès Discord trouvé dans le fichier .env ou dans les variables d’environnement")

# Création de l’activité
activity = Activity(name=ACTIVITY_NAME, type=ACTIVITY_TYPE) if ACTIVITY_TYPE and ACTIVITY_NAME else None

# Création des intents pour le client Discord
intents = Intents.default()
intents.message_content = True

# Création du client Discord
client = Client(activity=activity, intents=intents)

# Création de l’instance OpenAI
if MODEL.startswith("gpt-"):
    openai = OpenAI()
elif MODEL.startswith("gemini-"):
    openai = OpenAI(api_key=getenv("GEMINI_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
else:
    raise ValueError("Modèle non pris en charge. Veuillez utiliser un modèle GPT ou Gemini")


# Événement déclenché lorsque le bot est prêt
@client.event
async def on_ready():
    print(f"Connecté en tant que {client.user}")


# Événement déclenché lorsqu’un message est envoyé
@client.event
async def on_message(message):
    # Vérification que le message n’est pas envoyé par un bot et qu’il n’est pas vide
    if message.author.bot or not message.content:
        return
    # Vérification que le bot est mentionné dans le message ou que le message est envoyé dans un salon autorisé
    if client.user not in message.mentions and message.channel.id not in CHANNELS:
        return

    # Création de la liste des messages
    messages = [
        {
            "role": "system",
            "content": PROMPT,
        }
    ]

    # Envoi d’une indication que le bot est en train d’écrire
    async with message.channel.typing():
        # Récupération de l’historique des messages du salon
        async for msg in message.channel.history(limit=HISTORY_LENGTH):
            # Si le message a été envoyé par un autre bot ou est vide, on passe au suivant
            if (msg.author.bot and msg.author != client.user) or not msg.content:
                continue

            # Ajout du message et de son rôle à la liste des messages
            messages.append(
                {
                    "role": "assistant" if msg.author.bot else "user",
                    "content": msg.content,
                    "name": str(msg.author.id)
                }
            )

        # Inversion de l’ordre des messages
        messages.reverse()

        # Appel à l’API OpenAI pour générer une réponse
        completion = openai.chat.completions.create(
            model=MODEL,
            messages=messages,
        )

        # Envoi de la réponse générée par ChatGPT
        await message.reply(completion.choices[0].message.content)


# Démarrage du client Discord avec le jeton d’accès
client.run(DISCORD_TOKEN, log_handler=None)
