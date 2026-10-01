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
KEY_FILE = "keys.txt"

ADMIN_USERNAME = "w38r"

MIN_PAYOUT = 100
MAX_PAYOUT = 5000

KEY_PRICE = 1000


# =========================
# LOAD DATA
# =========================

def load_data():

    if not os.path.exists(DATA_FILE):
        return {
            "users": {},
            "settings": {
                "min_payout": 100,
                "max_payout": 5000,
                "key_price": 1000,
                "keys": []
            }
        }

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if "users" not in data:
            data["users"] = {}

        if "settings" not in data:
            data["settings"] = {}

        settings = data["settings"]

        if "min_payout" not in settings:
            settings["min_payout"] = 100

        if "max_payout" not in settings:
            settings["max_payout"] = 5000

        if "key_price" not in settings:
            settings["key_price"] = 1000

        if "keys" not in settings:
            settings["keys"] = []

        return data

    except (json.JSONDecodeError, OSError):

        return {
            "users": {},
            "settings": {
                "min_payout": 100,
                "max_payout": 5000,
                "key_price": 1000,
                "keys": []
            }
        }


data = load_data()

users = data["users"]

MIN_PAYOUT = data["settings"]["min_payout"]
MAX_PAYOUT = data["settings"]["max_payout"]

KEY_PRICE = data["settings"]["key_price"]

stored_keys = data["settings"]["keys"]


# =========================
# SAVE DATA
# =========================

def save_data():

    data = {
        "users": users,
        "settings": {
            "min_payout": MIN_PAYOUT,
            "max_payout": MAX_PAYOUT,
            "key_price": KEY_PRICE,
            "keys": stored_keys
        }
    }

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# =========================
# USER DATA
# =========================

def get_user(user_id):

    user_id = str(user_id)

    if user_id not in users:

        users[user_id] = {
            "robux": 0
        }

        save_data()

    if "robux" not in users[user_id]:
        users[user_id]["robux"] = 0

    return users[user_id]


# =========================
# ADMIN CHECK
# =========================

def is_admin(ctx):

    return ctx.author.name.lower() == ADMIN_USERNAME.lower()


# =========================
# BOT
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


# =========================
# READY
# =========================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print("Robux Simulator is online.")
    print(f"Key price: {KEY_PRICE:,} Robux")
    print(f"Keys in stock: {len(stored_keys):,}")


# =========================
# ROBUX
# =========================

@bot.command(name="robux")
async def robux(ctx):

    user = get_user(ctx.author.id)

    amount = random.randint(
        MIN_PAYOUT,
        MAX_PAYOUT
    )

    user["robux"] += amount

    save_data()

    await ctx.send(
        f"You earned {amount:,} Robux.\n"
        f"Your balance is {user['robux']:,} Robux."
    )


# =========================
# BALANCE
# =========================

@bot.command(name="bal", aliases=["balance"])
async def bal(ctx):

    user = get_user(ctx.author.id)

    await ctx.send(
        f"Your balance is {user['robux']:,} Robux."
    )


# =========================
# SET PAYOUT
# =========================

@bot.command(name="setpayout")
async def setpayout(
    ctx,
    minimum: int = None,
    maximum: int = None
):

    if not is_admin(ctx):

        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    if minimum is None or maximum is None:

        await ctx.send(
            "Usage: .setpayout <minimum> <maximum>"
        )
        return

    if minimum < 0 or maximum < 0:

        await ctx.send(
            "Payout amounts cannot be negative."
        )
        return

    if minimum > maximum:

        await ctx.send(
            "The minimum payout cannot be greater "
            "than the maximum payout."
        )
        return

    global MIN_PAYOUT
    global MAX_PAYOUT

    MIN_PAYOUT = minimum
    MAX_PAYOUT = maximum

    save_data()

    await ctx.send(
        f"Robux payout changed.\n"
        f"Minimum: {MIN_PAYOUT:,} Robux\n"
        f"Maximum: {MAX_PAYOUT:,} Robux"
    )


# =========================
# SET KEY PRICE
# =========================

@bot.command(name="key")
async def key(ctx, price: int = None):

    if not is_admin(ctx):

        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    if price is None:

        await ctx.send(
            "Usage: .key <price>"
        )
        return

    if price <= 0:

        await ctx.send(
            "The key price must be greater than 0."
        )
        return

    global KEY_PRICE

    KEY_PRICE = price

    save_data()

    await ctx.send(
        f"Key price set to {KEY_PRICE:,} Robux."
    )


# =========================
# KEY STOCK
# =========================

@bot.command(name="keystock")
async def keystock(ctx):

    await ctx.send(
        f"Keys in stock: {len(stored_keys):,}\n"
        f"Key price: {KEY_PRICE:,} Robux"
    )


# =========================
# RESTOCK KEYS
# =========================

@bot.command(name="restock")
async def restock(ctx):

    if not is_admin(ctx):

        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    if not os.path.exists(KEY_FILE):

        await ctx.send(
            "keys.txt was not found."
        )
        return

    try:

        with open(KEY_FILE, "r") as f:

            new_keys = [
                line.strip()
                for line in f.readlines()
                if line.strip()
            ]

    except OSError:

        await ctx.send(
            "I could not read keys.txt."
        )
        return

    if not new_keys:

        await ctx.send(
            "keys.txt is empty."
        )
        return

    added = 0

    for new_key in new_keys:

        if new_key not in stored_keys:

            stored_keys.append(new_key)
            added += 1

    save_data()

    await ctx.send(
        f"Restocked {added:,} key(s).\n"
        f"Current stock: {len(stored_keys):,} key(s)."
    )


# =========================
# BUY KEY
# =========================

@bot.command(name="buykey")
async def buykey(ctx):

    if len(stored_keys) <= 0:

        await ctx.send(
            "Keys are currently out of stock."
        )
        return

    user = get_user(ctx.author.id)

    if user["robux"] < KEY_PRICE:

        await ctx.send(
            f"You do not have enough Robux.\n"
            f"Key price: {KEY_PRICE:,} Robux\n"
            f"Your balance: {user['robux']:,} Robux"
        )
        return

    key_code = stored_keys.pop(0)

    user["robux"] -= KEY_PRICE

    save_data()

    try:

        await ctx.author.send(
            f"Your key:\n\n"
            f"{key_code}"
        )

        await ctx.send(
            f"Purchase successful.\n"
            f"Cost: {KEY_PRICE:,} Robux.\n"
            f"Your remaining balance is "
            f"{user['robux']:,} Robux.\n"
            f"The key was sent to your DMs."
        )

    except discord.Forbidden:

        # Give the key back if the bot cannot DM the player.
        stored_keys.insert(0, key_code)

        user["robux"] += KEY_PRICE

        save_data()

        await ctx.send(
            "I could not DM you your key. "
            "Please enable DMs from server members "
            "and try again."
        )


# =========================
# HELP
# =========================

@bot.command(name="help")
async def help_command(ctx):

    await ctx.send(
        "Robux Simulator Commands:\n\n"
        ".robux - Earn fictional Robux\n"
        ".bal - Check your Robux\n"
        ".key <price> - Admin: Set key price\n"
        ".buykey - Buy one key\n"
        ".keystock - Check key stock\n"
        ".restock - Admin: Load keys from keys.txt\n"
        ".setpayout <minimum> <maximum> - Admin command"
    )


# =========================
# ERROR HANDLER
# =========================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.send(
            "Invalid command arguments."
        )
        return

    print(
        f"Command error: {error}"
    )


# =========================
# FLASK KEEPALIVE
# =========================

app = Flask(__name__)


@app.route("/")
def home():

    return "Robux Simulator Bot is online."


def run_server():

    port = int(
        os.getenv(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================
# START BOT
# =========================

if not TOKEN:

    print(
        "ERROR: DISCORD_TOKEN is not set."
    )

else:

    Thread(
        target=run_server,
        daemon=True
    ).start()

    bot.run(TOKEN)
