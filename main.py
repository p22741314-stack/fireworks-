import json
import os
import random
import threading
import time

import discord
from discord.ext import commands
from flask import Flask


# ============================================================
# CONFIGURATION
# ============================================================

PREFIX = "."
DATA_FILE = "robux_users.json"

STARTING_ROBUX = 0

# Flask / Render
app = Flask(__name__)


@app.route("/")
def home():
    return "Robux Simulator Bot is online!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_web, daemon=True).start()


# ============================================================
# DATA STORAGE
# ============================================================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_user(user_id):
    data = load_data()
    uid = str(user_id)

    if uid not in data:
        data[uid] = {
            "robux": STARTING_ROBUX,
            "started": True,
            "games": [],
            "limiteds": [],
            "total_earned": 0,
            "total_donated": 0,
            "total_donated_received": 0,
            "created_at": time.time()
        }
        save_data(data)

    return data[uid]


def get_user(user_id):
    data = load_data()
    uid = str(user_id)

    if uid not in data:
        return None

    return data[uid]


def update_user(user_id, user_info):
    data = load_data()
    data[str(user_id)] = user_info
    save_data(data)


def ensure_started(ctx):
    user = get_user(ctx.author.id)

    if user is None:
        return None

    return user


# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Robux Simulator Bot is online!")


# ============================================================
# START
# ============================================================

@bot.command(name="start")
async def start(ctx):

    existing = get_user(ctx.author.id)

    if existing:
        embed = discord.Embed(
            title="🎮 Robux Simulator",
            description="You already have a simulator!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="💰 Balance",
            value=f"{existing['robux']:,} R$",
            inline=True
        )

        embed.add_field(
            name="🎮 Games",
            value=str(len(existing["games"])),
            inline=True
        )

        await ctx.send(embed=embed)
        return

    user = create_user(ctx.author.id)

    embed = discord.Embed(
        title="🎮 ROBUX SIMULATOR",
        description=(
            "Your simulator has started!\n\n"
            "You begin with **0 R$**.\n"
            "Build games, trade Limiteds, donate, and grow your fortune."
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="💰 Starting Balance",
        value="0 R$",
        inline=True
    )

    embed.add_field(
        name="🎮 Games",
        value="0",
        inline=True
    )

    embed.add_field(
        name="🎩 Limiteds",
        value="0",
        inline=True
    )

    embed.set_footer(text="Robux Simulator")

    await ctx.send(embed=embed)


# ============================================================
# BALANCE
# ============================================================

@bot.command(name="balance", aliases=["bal", "money"])
async def balance(ctx):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("You haven't started yet. Use `.start`.")
        return

    embed = discord.Embed(
        title=f"💰 {ctx.author.display_name}'s Balance",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Robux",
        value=f"**{user['robux']:,} R$**",
        inline=False
    )

    await ctx.send(embed=embed)


# ============================================================
# CREATE GAME
# ============================================================

@bot.command(name="game")
async def game(ctx, *, game_type=None):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    if not game_type:
        await ctx.send(
            "Choose a game type:\n"
            "🏃 Obby\n"
            "💰 Tycoon\n"
            "⚡ Simulator\n"
            "🧟 Survival\n\n"
            "Example: `.game survival`"
        )
        return

    game_type = game_type.lower()

    valid_games = {
        "obby": "🏃 Obby",
        "tycoon": "💰 Tycoon",
        "simulator": "⚡ Simulator",
        "survival": "🧟 Survival"
    }

    if game_type not in valid_games:
        await ctx.send(
            "Invalid game type. Choose:\n"
            "`obby`, `tycoon`, `simulator`, or `survival`."
        )
        return

    game_names = {
        "obby": "Mega Rainbow Obby",
        "tycoon": "Ultimate Tycoon",
        "simulator": "Speed Rush Simulator",
        "survival": "100 Days: Survival"
    }

    name = game_names[game_type]

    new_game = {
        "name": name,
        "type": game_type,
        "visits": 0,
        "likes": 0,
        "players": 0,
        "earnings": 0,
        "published": True,
        "created_at": time.time()
    }

    user["games"].append(new_game)
    update_user(ctx.author.id, user)

    embed = discord.Embed(
        title="🎮 GAME PUBLISHED!",
        description=f"**{name}** is now live!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Type",
        value=valid_games[game_type],
        inline=True
    )

    embed.add_field(
        name="👀 Visits",
        value="0",
        inline=True
    )

    embed.add_field(
        name="❤️ Likes",
        value="0",
        inline=True
    )

    await ctx.send(embed=embed)


# ============================================================
# VIEW GAMES
# ============================================================

@bot.command(name="games")
async def games(ctx):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    if not user["games"]:
        await ctx.send("You don't own any games yet. Use `.game survival`!")
        return

    embed = discord.Embed(
        title="🎮 Your Games",
        color=discord.Color.blue()
    )

    for game in user["games"]:
        embed.add_field(
            name=f"🎮 {game['name']}",
            value=(
                f"👀 Visits: **{game['visits']:,}**\n"
                f"❤️ Likes: **{game['likes']:,}**\n"
                f"👥 Players: **{game['players']:,}**\n"
                f"💰 Earnings: **{game['earnings']:,} R$**"
            ),
            inline=False
        )

    await ctx.send(embed=embed)


# ============================================================
# EARN FROM GAMES
# ============================================================

@bot.command(name="earn")
async def earn(ctx):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    if not user["games"]:
        await ctx.send("You don't have any games.")
        return

    total = 0

    for game in user["games"]:

        # Simulated earnings
        earnings = random.randint(100, 5000)

        visits = random.randint(100, 2500)
        likes = random.randint(10, max(20, visits // 3))
        players = random.randint(10, 1000)

        game["earnings"] += earnings
        game["visits"] += visits
        game["likes"] += likes
        game["players"] = players

        total += earnings

    user["robux"] += total
    user["total_earned"] += total

    update_user(ctx.author.id, user)

    embed = discord.Embed(
        title="📈 Game Earnings",
        description=f"You earned **{total:,} R$** from your games!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="💰 New Balance",
        value=f"{user['robux']:,} R$",
        inline=False
    )

    await ctx.send(embed=embed)


# ============================================================
# DONATE
# ============================================================

@bot.command(name="donate")
async def donate(ctx, member: discord.Member = None, amount: int = None):

    if member is None or amount is None:
        await ctx.send(
            "Usage: `.donate @player amount`\n"
            "Example: `.donate @Steve 5000`"
        )
        return

    if amount <= 0:
        await ctx.send("Donation must be greater than 0.")
        return

    if member.id == ctx.author.id:
        await ctx.send("You can't donate to yourself.")
        return

    sender = ensure_started(ctx)

    if sender is None:
        await ctx.send("Use `.start` first.")
        return

    receiver = get_user(member.id)

    if receiver is None:
        receiver = create_user(member.id)

    if sender["robux"] < amount:
        await ctx.send(
            f"You only have **{sender['robux']:,} R$**."
        )
        return

    sender["robux"] -= amount
    receiver["robux"] += amount

    sender["total_donated"] += amount
    receiver["total_donated_received"] += amount

    update_user(ctx.author.id, sender)
    update_user(member.id, receiver)

    embed = discord.Embed(
        title="🎁 Donation Sent!",
        description=(
            f"{ctx.author.mention} donated "
            f"**{amount:,} R$** to {member.mention}!"
        ),
        color=discord.Color.purple()
    )

    embed.add_field(
        name="Your Balance",
        value=f"{sender['robux']:,} R$",
        inline=True
    )

    embed.add_field(
        name="Recipient Balance",
        value=f"{receiver['robux']:,} R$",
        inline=True
    )

    await ctx.send(embed=embed)


# ============================================================
# LIMITED
# ============================================================

@bot.command(name="limited")
async def limited(ctx):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    if not user["limiteds"]:
        await ctx.send("🎩 You don't own any Limiteds.")
        return

    embed = discord.Embed(
        title="🎩 Your Limiteds",
        color=discord.Color.gold()
    )

    for i, limited in enumerate(user["limiteds"], 1):

        embed.add_field(
            name=f"#{i} — {limited['name']}",
            value=(
                f"Purchase price: **{limited['purchase_price']:,} R$**\n"
                f"Current value: **{limited['value']:,} R$**"
            ),
            inline=False
        )

    await ctx.send(embed=embed)


# ============================================================
# BUY LIMITED
# ============================================================

@bot.command(name="buylimited")
async def buylimited(ctx, price: int = None):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    if price is None:
        await ctx.send("Usage: `.buylimited 5000`")
        return

    if price <= 0:
        await ctx.send("Price must be greater than 0.")
        return

    if user["robux"] < price:
        await ctx.send(
            f"You need **{price:,} R$**, but only have "
            f"**{user['robux']:,} R$**."
        )
        return

    user["robux"] -= price

    limited = {
        "name": f"Limited #{random.randint(1000, 9999)}",
        "purchase_price": price,
        "value": price
    }

    user["limiteds"].append(limited)

    update_user(ctx.author.id, user)

    embed = discord.Embed(
        title="🎩 Limited Purchased!",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Item",
        value=limited["name"],
        inline=False
    )

    embed.add_field(
        name="Price",
        value=f"{price:,} R$",
        inline=True
    )

    embed.add_field(
        name="Balance",
        value=f"{user['robux']:,} R$",
        inline=True
    )

    await ctx.send(embed=embed)


# ============================================================
# SELL LIMITED
# ============================================================

@bot.command(name="selllimited")
async def selllimited(ctx, index: int = None, value: int = None):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    if not user["limiteds"]:
        await ctx.send("You don't own any Limiteds.")
        return

    if index is None or value is None:
        await ctx.send(
            "Usage: `.selllimited <number> <value>`\n"
            "Example: `.selllimited 1 25000`"
        )
        return

    if index < 1 or index > len(user["limiteds"]):
        await ctx.send("Invalid Limited number.")
        return

    if value <= 0:
        await ctx.send("Sale value must be greater than 0.")
        return

    limited = user["limiteds"].pop(index - 1)

    purchase_price = limited["purchase_price"]

    user["robux"] += value

    update_user(ctx.author.id, user)

    profit = value - purchase_price

    embed = discord.Embed(
        title="🎩 Limited Sold!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Sale Price",
        value=f"{value:,} R$",
        inline=True
    )

    embed.add_field(
        name="Purchase Price",
        value=f"{purchase_price:,} R$",
        inline=True
    )

    embed.add_field(
        name="Profit",
        value=f"{profit:,} R$",
        inline=True
    )

    embed.add_field(
        name="New Balance",
        value=f"{user['robux']:,} R$",
        inline=False
    )

    await ctx.send(embed=embed)


# ============================================================
# DOUBLE OR NOTHING
# ============================================================

@bot.command(name="double")
async def double(ctx, choice: str = None):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    if user["robux"] <= 0:
        await ctx.send("You have no R$ to put on the line.")
        return

    if choice is None:
        await ctx.send(
            "🎲 Choose heads or tails:\n"
            "`.double heads`\n"
            "`.double tails`"
        )
        return

    choice = choice.lower()

    if choice not in ["heads", "tails"]:
        await ctx.send("Choose `heads` or `tails`.")
        return

    result = random.choice(["heads", "tails"])
    amount = user["robux"]

    if choice == result:

        winnings = amount * 2
        user["robux"] = winnings

        update_user(ctx.author.id, user)

        embed = discord.Embed(
            title="🪙 YOU WIN!",
            description=(
                f"The coin landed on **{result.upper()}**!\n\n"
                f"💰 **{winnings:,} R$**"
            ),
            color=discord.Color.green()
        )

    else:

        user["robux"] = 0

        update_user(ctx.author.id, user)

        embed = discord.Embed(
            title="🪙 YOU LOST!",
            description=(
                f"The coin landed on **{result.upper()}**.\n\n"
                "💸 You lost everything."
            ),
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


# ============================================================
# SAVE
# ============================================================

@bot.command(name="save")
async def save(ctx):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    update_user(ctx.author.id, user)

    await ctx.send(
        f"💰 Your **{user['robux']:,} R$** has been saved!"
    )


# ============================================================
# STATS
# ============================================================

@bot.command(name="stats")
async def stats(ctx):

    user = ensure_started(ctx)

    if user is None:
        await ctx.send("Use `.start` first.")
        return

    embed = discord.Embed(
        title=f"📊 {ctx.author.display_name}'s Simulator",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="💰 Robux",
        value=f"{user['robux']:,} R$",
        inline=True
    )

    embed.add_field(
        name="🎮 Games",
        value=str(len(user["games"])),
        inline=True
    )

    embed.add_field(
        name="🎩 Limiteds",
        value=str(len(user["limiteds"])),
        inline=True
    )

    embed.add_field(
        name="📈 Total Earned",
        value=f"{user['total_earned']:,} R$",
        inline=True
    )

    embed.add_field(
        name="🎁 Total Donated",
        value=f"{user['total_donated']:,} R$",
        inline=True
    )

    embed.add_field(
        name="🎁 Donations Received",
        value=f"{user['total_donated_received']:,} R$",
        inline=True
    )

    await ctx.send(embed=embed)


# ============================================================
# LEADERBOARD
# ============================================================

@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx):

    data = load_data()

    if not data:
        await ctx.send("Nobody has started the simulator yet.")
        return

    sorted_users = sorted(
        data.items(),
        key=lambda x: x[1].get("robux", 0),
        reverse=True
    )

    embed = discord.Embed(
        title="🏆 Robux Simulator Leaderboard",
        color=discord.Color.gold()
    )

    for position, (user_id, user) in enumerate(sorted_users[:10], 1):

        try:
            member = ctx.guild.get_member(int(user_id))

            if member:
                name = member.display_name
            else:
                name = f"User {user_id}"

        except:
            name = f"User {user_id}"

        embed.add_field(
            name=f"{position}. {name}",
            value=f"💰 {user['robux']:,} R$",
            inline=False
        )

    await ctx.send(embed=embed)


# ============================================================
# RESET YOUR ACCOUNT
# ============================================================

@bot.command(name="reset")
async def reset(ctx):

    data = load_data()
    uid = str(ctx.author.id)

    if uid not in data:
        await ctx.send("You don't have a simulator account.")
        return

    del data[uid]
    save_data(data)

    await ctx.send(
        "🔄 Your simulator has been reset.\n"
        "Use `.start` to begin again with **0 R$**."
    )


# ============================================================
# ADMIN: ADD ROBUX
# ============================================================

@bot.command(name="adminadd")
async def adminadd(ctx, member: discord.Member = None, amount: int = None):

    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Administrator permission required.")
        return

    if member is None or amount is None:
        await ctx.send(
            "Usage: `.adminadd @user amount`"
        )
        return

    if amount <= 0:
        await ctx.send("Amount must be greater than 0.")
        return

    user = get_user(member.id)

    if user is None:
        user = create_user(member.id)

    user["robux"] += amount

    update_user(member.id, user)

    await ctx.send(
        f"💰 Added **{amount:,} R$** to {member.mention}.\n"
        f"New balance: **{user['robux']:,} R$**"
    )


# ============================================================
# ADMIN: RESET USER
# ============================================================

@bot.command(name="adminreset")
async def adminreset(ctx, member: discord.Member = None):

    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Administrator permission required.")
        return

    if member is None:
        await ctx.send("Usage: `.adminreset @user`")
        return

    data = load_data()
    uid = str(member.id)

    if uid in data:
        del data[uid]
        save_data(data)

    await ctx.send(
        f"🔄 Reset {member.mention}'s simulator account."
    )


# ============================================================
# HELP
# ============================================================

@bot.command(name="simhelp")
async def simhelp(ctx):

    embed = discord.Embed(
        title="🎮 Robux Simulator Commands",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="👤 Account",
        value=(
            "`.start`\n"
            "`.balance`\n"
            "`.stats`\n"
            "`.save`\n"
            "`.reset`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎮 Games",
        value=(
            "`.game survival`\n"
            "`.games`\n"
            "`.earn`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎩 Limiteds",
        value=(
            "`.limited`\n"
            "`.buylimited 500`\n"
            "`.selllimited 1 25000`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎁 Social",
        value=(
            "`.donate @user 5000`\n"
            "`.leaderboard`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎲 Gambling",
        value=(
            "`.double heads`\n"
            "`.double tails`"
        ),
        inline=True
    )

    await ctx.send(embed=embed)


# ============================================================
# ERROR HANDLING
# ============================================================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Missing argument: `{error.param.name}`"
        )
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send(
            "❌ I couldn't understand that argument."
        )
        return

    print(f"Command error: {error}")


# ============================================================
# RUN BOT
# ============================================================

if __name__ == "__main__":

    token = os.environ.get("DISCORD_TOKEN")

    # Optional token.txt support
    if not token and os.path.exists("token.txt"):
        with open("token.txt", "r", encoding="utf-8") as f:
            token = f.read().strip()

    if not token:
        raise SystemExit(
            "No bot token found. "
            "Set DISCORD_TOKEN in your Render environment variables."
        )

    bot.run(token)
