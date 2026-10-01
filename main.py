import discord
from discord.ext import commands
import random
import json
import os
from flask import Flask
from threading import Thread

# =========================
# SETTINGS
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    try:
        with open("token.txt", "r") as f:
            TOKEN = f.read().strip()
    except FileNotFoundError:
        TOKEN = None

PREFIX = "."
DATA_FILE = "robux_users.json"

# =========================
# DATA
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=4)


users = load_data()


def get_user(user_id):
    user_id = str(user_id)

    if user_id not in users:
        users[user_id] = {
            "robux": 0
        }
        save_data()

    return users[user_id]


# =========================
# DISCORD BOT
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Robux Simulator is online.")


# =========================
# ROBUX COMMAND
# =========================

@bot.command(name="robux")
async def robux(ctx):
    user = get_user(ctx.author.id)

    amount = random.randint(100, 5000)

    user["robux"] += amount
    save_data()

    await ctx.send(
        f"You earned {amount:,} Robux.\n"
        f"Your balance is {user['robux']:,} Robux."
    )


# =========================
# GAMBLE COMMAND
# =========================

@bot.command(name="gamble")
async def gamble(ctx, amount: int = None):

    if amount is None:
        await ctx.send(
            "Usage: .gamble <amount>"
        )
        return

    if amount <= 0:
        await ctx.send(
            "The amount must be greater than 0."
        )
        return

    user = get_user(ctx.author.id)

    if user["robux"] < amount:
        await ctx.send(
            f"You do not have enough Robux.\n"
            f"Your balance is {user['robux']:,} Robux."
        )
        return

    won = random.choice([True, False])

    if won:
        user["robux"] += amount

        await ctx.send(
            f"You won {amount:,} Robux.\n"
            f"Your balance is {user['robux']:,} Robux."
        )

    else:
        user["robux"] -= amount

        await ctx.send(
            f"You lost {amount:,} Robux.\n"
            f"Your balance is {user['robux']:,} Robux."
        )

    save_data()


# =========================
# HELP
# =========================

@bot.command(name="help")
async def help_command(ctx):
    await ctx.send(
        "Robux Simulator Commands:\n\n"
        ".robux - Earn random Robux\n"
        ".gamble <amount> - Gamble your Robux"
    )


# =========================
# FLASK SERVER
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "Robux Simulator Bot is online."


def run_server():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================
# START BOT
# =========================

if not TOKEN:
    print("ERROR: DISCORD_TOKEN is not set.")
else:
    Thread(target=run_server).start()
    bot.run(TOKEN)
