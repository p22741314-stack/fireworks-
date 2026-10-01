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

MIN_PAYOUT = 100
MAX_PAYOUT = 5000

ADMIN_USERNAME = "w38r"


# =========================
# DATA
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "users": {},
            "settings": {
                "min_payout": 100,
                "max_payout": 5000
            }
        }

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        if "users" not in data:
            data["users"] = {}

        if "settings" not in data:
            data["settings"] = {}

        if "min_payout" not in data["settings"]:
            data["settings"]["min_payout"] = 100

        if "max_payout" not in data["settings"]:
            data["settings"]["max_payout"] = 5000

        return data

    except (json.JSONDecodeError, OSError):
        return {
            "users": {},
            "settings": {
                "min_payout": 100,
                "max_payout": 5000
            }
        }


data = load_data()

users = data["users"]

MIN_PAYOUT = data["settings"]["min_payout"]
MAX_PAYOUT = data["settings"]["max_payout"]


# =========================
# SAVE DATA
# =========================

def save_data():
    data = {
        "users": users,
        "settings": {
            "min_payout": MIN_PAYOUT,
            "max_payout": MAX_PAYOUT
        }
    }

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# =========================
# GET USER
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
# FIND W38R BANK
# =========================

def get_bank_user():

    # Look through users currently known to the bot
    for guild in bot.guilds:

        for member in guild.members:

            if member.name.lower() == ADMIN_USERNAME.lower():

                return get_user(member.id)

    return None


# =========================
# BOT
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

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

    bank = get_bank_user()

    if bank is None:
        print("WARNING: Could not find the w38r account.")
    else:
        print("w38r bank account found.")


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

@bot.command(name="balance", aliases=["bal"])
async def balance(ctx):

    user = get_user(ctx.author.id)

    await ctx.send(
        f"Your balance is {user['robux']:,} Robux."
    )


# =========================
# GAMBLE
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

    player = get_user(ctx.author.id)

    if player["robux"] < amount:
        await ctx.send(
            f"You do not have enough Robux.\n"
            f"Your balance is {player['robux']:,} Robux."
        )
        return

    # Find w38r's account
    bank = get_bank_user()

    if bank is None:
        await ctx.send(
            "The w38r bank has not been configured."
        )
        return

    won = random.choice([True, False])

    # =========================
    # PLAYER WINS
    # =========================

    if won:

        # Bank pays the player
        if bank["robux"] < amount:

            await ctx.send(
                "The w38r bank does not have enough "
                "Robux to pay this win."
            )

            return

        player["robux"] += amount
        bank["robux"] -= amount

        await ctx.send(
            f"You won {amount:,} Robux.\n"
            f"Your balance is {player['robux']:,} Robux."
        )

    # =========================
    # PLAYER LOSES
    # =========================

    else:

        # Remove money from player
        player["robux"] -= amount

        # Put ALL lost money into w38r's bank
        bank["robux"] += amount

        await ctx.send(
            f"You lost {amount:,} Robux.\n"
            f"Your balance is {player['robux']:,} Robux."
        )

    save_data()


# =========================
# BANK
# =========================

@bot.command(name="bank")
async def bank(ctx):

    if ctx.author.name.lower() != ADMIN_USERNAME.lower():
        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    bank_user = get_bank_user()

    if bank_user is None:
        await ctx.send(
            "I could not find the w38r account."
        )
        return

    await ctx.send(
        f"w38r Bank Balance: "
        f"{bank_user['robux']:,} Robux"
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

    if ctx.author.name.lower() != ADMIN_USERNAME.lower():
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
        f"Minimum payout: {MIN_PAYOUT:,} Robux\n"
        f"Maximum payout: {MAX_PAYOUT:,} Robux"
    )


# =========================
# HELP
# =========================

@bot.command(name="help")
async def help_command(ctx):

    await ctx.send(
        "Robux Simulator Commands:\n\n"
        ".robux - Earn fictional Robux\n"
        ".balance - Check your Robux\n"
        ".gamble <amount> - Gamble Robux\n"
        ".bank - View the w38r bank\n"
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
