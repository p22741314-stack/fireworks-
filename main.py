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

# Default Robux payout
MIN_PAYOUT = 100
MAX_PAYOUT = 5000

# Only this username can use admin commands
ADMIN_USERNAME = "w38r"


# =========================
# DATA
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "users": {},
            "shop": {}
        }

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        # Make sure both sections exist
        if "users" not in data:
            data["users"] = {}

        if "shop" not in data:
            data["shop"] = {}

        return data

    except (json.JSONDecodeError, OSError):
        return {
            "users": {},
            "shop": {}
        }


def save_data():
    data = {
        "users": users,
        "shop": shop
    }

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


data = load_data()

users = data["users"]
shop = data["shop"]


def get_user(user_id):
    user_id = str(user_id)

    if user_id not in users:
        users[user_id] = {
            "robux": 0,
            "inventory": {}
        }
        save_data()

    # Add inventory if old account doesn't have one
    if "inventory" not in users[user_id]:
        users[user_id]["inventory"] = {}
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
# .SHOP
# =========================

@bot.command(name="shop")
async def shop_command(ctx):

    if not shop:
        await ctx.send("The shop is currently empty.")
        return

    message = "Shop:\n\n"

    for item_name, item_data in shop.items():

        buy_price = item_data["buy_price"]
        sell_price = item_data["sell_price"]

        message += (
            f"{item_name}\n"
            f"Buy: {buy_price:,} Robux\n"
            f"Sell: {sell_price:,} Robux\n\n"
        )

    await ctx.send(message)


# =========================
# .ADDITEM
# =========================

@bot.command(name="additem")
async def additem(ctx, buy_price: int = None, sell_price: int = None, *, item_name: str = None):

    # Only w38r
    if ctx.author.name != ADMIN_USERNAME:
        await ctx.send("You do not have permission to use this command.")
        return

    if item_name is None or buy_price is None or sell_price is None:
        await ctx.send(
            "Usage: .additem <buy price> <sell price> <item name>"
        )
        return

    if buy_price <= 0:
        await ctx.send("The buy price must be greater than 0.")
        return

    if sell_price <= 0:
        await ctx.send("The sell price must be greater than 0.")
        return

    if sell_price <= buy_price:
        await ctx.send(
            "The sell price must be greater than the buy price."
        )
        return

    item_name = item_name.strip()

    if not item_name:
        await ctx.send("You must provide an item name.")
        return

    if len(item_name) > 50:
        await ctx.send("The item name cannot be longer than 50 characters.")
        return

    # Prevent duplicate item names
    if item_name.lower() in [name.lower() for name in shop]:
        await ctx.send("That item already exists in the shop.")
        return

    shop[item_name] = {
        "buy_price": buy_price,
        "sell_price": sell_price
    }

    save_data()

    await ctx.send(
        f"Item added to the shop.\n"
        f"Item: {item_name}\n"
        f"Buy price: {buy_price:,} Robux\n"
        f"Sell price: {sell_price:,} Robux"
    )


# =========================
# .BUY
# =========================

@bot.command(name="buy")
async def buy(ctx, *, item_name: str = None):

    if item_name is None:
        await ctx.send("Usage: .buy <item>")
        return

    user = get_user(ctx.author.id)

    # Find item without caring about capitalization
    actual_item = None

    for name in shop:
        if name.lower() == item_name.lower():
            actual_item = name
            break

    if actual_item is None:
        await ctx.send("That item is not in the shop.")
        return

    item = shop[actual_item]
    price = item["buy_price"]

    if user["robux"] < price:
        await ctx.send(
            f"You do not have enough Robux.\n"
            f"Price: {price:,} Robux\n"
            f"Your balance: {user['robux']:,} Robux"
        )
        return

    user["robux"] -= price

    if actual_item not in user["inventory"]:
        user["inventory"][actual_item] = 0

    user["inventory"][actual_item] += 1

    save_data()

    await ctx.send(
        f"You bought {actual_item} for {price:,} Robux.\n"
        f"Your balance is {user['robux']:,} Robux."
    )


# =========================
# .SELL
# =========================

@bot.command(name="sell")
async def sell(ctx, *, item_name: str = None):

    if item_name is None:
        await ctx.send("Usage: .sell <item>")
        return

    user = get_user(ctx.author.id)

    # Find item without caring about capitalization
    actual_item = None

    for name in shop:
        if name.lower() == item_name.lower():
            actual_item = name
            break

    if actual_item is None:
        await ctx.send("That item does not exist.")
        return

    # Check inventory
    if actual_item not in user["inventory"]:
        await ctx.send(
            f"You do not own {actual_item}."
        )
        return

    if user["inventory"][actual_item] <= 0:
        await ctx.send(
            f"You do not own {actual_item}."
        )
        return

    item = shop[actual_item]
    sell_price = item["sell_price"]

    # Remove one item
    user["inventory"][actual_item] -= 1

    # Remove empty inventory entry
    if user["inventory"][actual_item] <= 0:
        del user["inventory"][actual_item]

    # Give Robux
    user["robux"] += sell_price

    save_data()

    await ctx.send(
        f"You sold {actual_item} for {sell_price:,} Robux.\n"
        f"Your balance is {user['robux']:,} Robux."
    )


# =========================
# .INVENTORY
# =========================

@bot.command(name="inventory")
async def inventory(ctx):

    user = get_user(ctx.author.id)

    inventory = user["inventory"]

    if not inventory:
        await ctx.send("Your inventory is empty.")
        return

    message = "Your inventory:\n\n"

    for item_name, amount in inventory.items():
        message += f"{item_name}: {amount}\n"

    await ctx.send(message)


# =========================
# ADMIN .SETPAYOUT
# =========================

@bot.command(name="setpayout")
async def setpayout(ctx, minimum: int = None, maximum: int = None):

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
        ".shop - View the shop\n"
        ".buy <item> - Buy an item\n"
        ".sell <item> - Sell an item\n"
        ".inventory - View your items\n"
        ".additem <buy price> <sell price> <item name> - Admin command\n"
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
