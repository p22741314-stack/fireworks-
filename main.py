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

# Default .robux payout
MIN_PAYOUT = 100
MAX_PAYOUT = 5000

# Only this Discord username can use .setpayout
ADMIN_USERNAME = "w38r"


# =========================
# DATA
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
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
# .ROBUX
# =========================

@bot.command(name="robux")
async def robux(ctx):
    user = get_user(ctx.author.id)

    amount = random.randint(MIN_PAYOUT, MAX_PAYOUT)

    user["robux"] += amount

    save_data()

    await ctx.send(
        f"You earned {amount:,} Robux.\n"
        f"Your balance is {user['robux']:,} Robux."
    )


# =========================
# .GAMBLE
# =========================

@bot.command(name="gamble")
async def gamble(ctx, amount: int = None):

    if amount is None:
        await ctx.send("Usage: .gamble <amount>")
        return

    if amount <= 0:
        await ctx.send("The amount must be greater than 0.")
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
# ADMIN .SETPAYOUT
# =========================

@bot.command(name="setpayout")
async def setpayout(ctx, minimum: int = None, maximum: int = None):

    # Only username "w38r" can use this command
    if ctx.author.name != ADMIN_USERNAME:
        await ctx.send("You do not have permission to use this command.")
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
            "The minimum payout cannot be greater than the maximum payout."
        )
        return

    global MIN_PAYOUT
    global MAX_PAYOUT

    MIN_PAYOUT = minimum
    MAX_PAYOUT = maximum

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
        ".robux - Earn random Robux\n"
        ".gamble <amount> - Gamble your Robux\n"
        ".setpayout <minimum> <maximum> - Admin command"
    )


# =========================
# UNKNOWN COMMAND HANDLER
# =========================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("Invalid command arguments.")
        return

    print(f"Command error: {error}")


# =========================
# FLASK SERVER
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "Robux Simulator Bot is online."


def run_server():
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================
# START BOT
# =========================

if not TOKEN:
    print("ERROR: DISCORD_TOKEN is not set.")
else:
    Thread(
        target=run_server,
        daemon=True
    ).start()

    bot.run(TOKEN)
