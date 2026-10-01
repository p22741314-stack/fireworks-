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

# Put the Discord User ID of w38r into Render:
# W38R_USER_ID=123456789012345678
try:
    ADMIN_USER_ID = int(os.getenv("W38R_USER_ID", "0"))
except ValueError:
    ADMIN_USER_ID = 0

HR_KEY_PRICE = 1000
HR_KEY_STOCK = 0


# =========================
# DATA
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "users": {},
            "settings": {
                "hr_key_price": 1000,
                "hr_key_stock": 0,
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

        if "hr_key_price" not in data["settings"]:
            data["settings"]["hr_key_price"] = 1000

        if "hr_key_stock" not in data["settings"]:
            data["settings"]["hr_key_stock"] = 0

        if "min_payout" not in data["settings"]:
            data["settings"]["min_payout"] = 100

        if "max_payout" not in data["settings"]:
            data["settings"]["max_payout"] = 5000

        return data

    except (json.JSONDecodeError, OSError):
        return {
            "users": {},
            "settings": {
                "hr_key_price": 1000,
                "hr_key_stock": 0,
                "min_payout": 100,
                "max_payout": 5000
            }
        }


data = load_data()

users = data["users"]

HR_KEY_PRICE = data["settings"]["hr_key_price"]
HR_KEY_STOCK = data["settings"]["hr_key_stock"]

MIN_PAYOUT = data["settings"]["min_payout"]
MAX_PAYOUT = data["settings"]["max_payout"]


def save_data():
    data = {
        "users": users,
        "settings": {
            "hr_key_price": HR_KEY_PRICE,
            "hr_key_stock": HR_KEY_STOCK,
            "min_payout": MIN_PAYOUT,
            "max_payout": MAX_PAYOUT
        }
    }

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_user(user_id):
    user_id = str(user_id)

    if user_id not in users:
        users[user_id] = {
            "robux": 0,
            "hr_keys": 0
        }
        save_data()

    if "robux" not in users[user_id]:
        users[user_id]["robux"] = 0

    if "hr_keys" not in users[user_id]:
        users[user_id]["hr_keys"] = 0

    return users[user_id]


# =========================
# BANK
# =========================

def get_bank():
    if ADMIN_USER_ID == 0:
        return None

    return get_user(ADMIN_USER_ID)


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

    if ADMIN_USER_ID == 0:
        print("WARNING: W38R_USER_ID is not configured.")
    else:
        print(f"Bank account configured for Discord ID: {ADMIN_USER_ID}")


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
# GAMBLE
# =========================

@bot.command(name="gamble")
async def gamble(ctx, amount: int = None):

    if amount is None:
        await ctx.send("Usage: .gamble <amount>")
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

    bank = get_bank()

    if bank is None:
        await ctx.send(
            "The w38r bank account has not been configured."
        )
        return

    won = random.choice([True, False])

    # =========================
    # PLAYER WINS
    # =========================

    if won:

        # The bank must have enough money
        # to pay the player.

        if bank["robux"] < amount:
            await ctx.send(
                "The w38r bank does not have enough "
                "Robux to pay this win."
            )
            return

        user["robux"] += amount
        bank["robux"] -= amount

        await ctx.send(
            f"You won {amount:,} Robux.\n"
            f"Your balance is {user['robux']:,} Robux."
        )

    # =========================
    # PLAYER LOSES
    # =========================

    else:

        user["robux"] -= amount

        # ALL LOST MONEY GOES
        # INTO THE W38R BANK

        bank["robux"] += amount

        await ctx.send(
            f"You lost {amount:,} Robux.\n"
            f"Your balance is {user['robux']:,} Robux."
        )

    save_data()


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
# BANK
# =========================

@bot.command(name="bank")
async def bank_command(ctx):

    if ctx.author.name != ADMIN_USERNAME:
        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    bank = get_bank()

    if bank is None:
        await ctx.send(
            "The w38r bank account has not been configured."
        )
        return

    await ctx.send(
        f"w38r Bank Balance: {bank['robux']:,} Robux"
    )


# =========================
# KEYS
# =========================

@bot.command(name="keys")
async def keys(ctx):

    if HR_KEY_STOCK <= 0:
        stock_text = "OUT OF STOCK"
    else:
        stock_text = f"{HR_KEY_STOCK:,}"

    await ctx.send(
        f"HR Key\n"
        f"Price: {HR_KEY_PRICE:,} Robux\n"
        f"Stock: {stock_text}"
    )


# =========================
# BUY KEY
# =========================

@bot.command(name="buykey")
async def buykey(ctx, amount: int = None):

    global HR_KEY_STOCK

    if amount is None:
        await ctx.send(
            "Usage: .buykey <amount>"
        )
        return

    if amount <= 0:
        await ctx.send(
            "The amount must be greater than 0."
        )
        return

    user = get_user(ctx.author.id)

    if HR_KEY_STOCK < amount:
        await ctx.send(
            f"There are not enough HR Keys in stock.\n"
            f"Available: {HR_KEY_STOCK:,}"
        )
        return

    total_price = HR_KEY_PRICE * amount

    if user["robux"] < total_price:
        await ctx.send(
            f"You do not have enough Robux.\n"
            f"Price: {total_price:,} Robux\n"
            f"Your balance: {user['robux']:,} Robux"
        )
        return

    user["robux"] -= total_price

    HR_KEY_STOCK -= amount

    user["hr_keys"] += amount

    save_data()

    await ctx.send(
        f"You bought {amount:,} HR Key(s).\n"
        f"Cost: {total_price:,} Robux\n"
        f"Your balance: {user['robux']:,} Robux\n"
        f"Remaining stock: {HR_KEY_STOCK:,}"
    )


# =========================
# MY KEYS
# =========================

@bot.command(name="mykeys")
async def mykeys(ctx):

    user = get_user(ctx.author.id)

    await ctx.send(
        f"You own {user['hr_keys']:,} HR Key(s)."
    )


# =========================
# RESTOCK
# =========================

@bot.command(name="restock")
async def restock(ctx, amount: int = None):

    if ctx.author.name != ADMIN_USERNAME:
        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    if amount is None:
        await ctx.send(
            "Usage: .restock <amount>"
        )
        return

    if amount <= 0:
        await ctx.send(
            "The restock amount must be greater than 0."
        )
        return

    global HR_KEY_STOCK

    HR_KEY_STOCK += amount

    save_data()

    await ctx.send(
        f"Restocked {amount:,} HR Key(s).\n"
        f"Current stock: {HR_KEY_STOCK:,}"
    )


# =========================
# SET KEY PRICE
# =========================

@bot.command(name="setkeyprice")
async def setkeyprice(ctx, price: int = None):

    if ctx.author.name != ADMIN_USERNAME:
        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    if price is None:
        await ctx.send(
            "Usage: .setkeyprice <price>"
        )
        return

    if price <= 0:
        await ctx.send(
            "The key price must be greater than 0."
        )
        return

    global HR_KEY_PRICE

    HR_KEY_PRICE = price

    save_data()

    await ctx.send(
        f"HR Key price changed to "
        f"{HR_KEY_PRICE:,} Robux."
    )


# =========================
# KEY EMBED
# =========================

@bot.command(name="keyembed")
async def keyembed(ctx):

    if ctx.author.name != ADMIN_USERNAME:
        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    if HR_KEY_STOCK <= 0:
        stock_text = "OUT OF STOCK"
    else:
        stock_text = f"{HR_KEY_STOCK:,}"

    embed = discord.Embed(
        title="HR Key",
        description="Purchase HR Keys using your Robux.",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Price",
        value=f"{HR_KEY_PRICE:,} Robux",
        inline=True
    )

    embed.add_field(
        name="Stock",
        value=stock_text,
        inline=True
    )

    embed.add_field(
        name="Purchase",
        value=".buykey <amount>",
        inline=False
    )

    await ctx.send(embed=embed)


# =========================
# SET PAYOUT
# =========================

@bot.command(name="setpayout")
async def setpayout(
    ctx,
    minimum: int = None,
    maximum: int = None
):

    if ctx.author.name != ADMIN_USERNAME:
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
        ".keys - View HR Key price and stock\n"
        ".buykey <amount> - Buy HR Keys\n"
        ".mykeys - View your HR Keys\n"
        ".bank - View the w38r bank balance\n"
        ".restock <amount> - Admin command\n"
        ".setkeyprice <price> - Admin command\n"
        ".keyembed - Admin command\n"
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
# FLASK SERVER
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
