import discord
from discord.ext import commands
import sqlite3
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "keys.db"


# ---------------- DATABASE ----------------

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_keys(keys):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    added = 0

    for key in keys:
        try:
            cursor.execute(
                "INSERT INTO keys (key) VALUES (?)",
                (key,)
            )
            added += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()

    return added


def get_key():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, key FROM keys ORDER BY id LIMIT 1"
    )

    result = cursor.fetchone()

    if result is None:
        conn.close()
        return None

    key_id, key = result

    cursor.execute(
        "DELETE FROM keys WHERE id = ?",
        (key_id,)
    )

    conn.commit()
    conn.close()

    return key


def get_stock():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM keys")
    count = cursor.fetchone()[0]

    conn.close()

    return count


def get_all_keys():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT key FROM keys ORDER BY id")
    keys = [row[0] for row in cursor.fetchall()]

    conn.close()

    return keys


def remove_key(key):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM keys WHERE key = ?",
        (key,)
    )

    removed = cursor.rowcount

    conn.commit()
    conn.close()

    return removed


# ---------------- BOT ----------------

@bot.event
async def on_ready():
    setup_database()
    print(f"Logged in as {bot.user}")
    print(f"Key stock: {get_stock()}")


# ---------------- GET KEY ----------------

@bot.command()
async def getkey(ctx):

    key = get_key()

    if key is None:
        await ctx.send("❌ **Out of stock!**")
        return

    try:
        await ctx.author.send(
            f"🎉 **Your Key**\n\n"
            f"`{key}`\n\n"
            f"🔑 Enjoy!"
        )

        await ctx.send(
            f"✅ {ctx.author.mention}, your key was sent to your DMs!"
        )

    except discord.Forbidden:
        await ctx.send(
            f"❌ {ctx.author.mention}, I can't DM you. "
            f"Please enable DMs and try again."
        )


# ---------------- STOCK ----------------

@bot.command()
async def stock(ctx):

    amount = get_stock()

    await ctx.send(
        f"📦 **Key Stock**\n\n"
        f"🔑 Available: **{amount}**"
    )


# ---------------- RESTOCK ----------------

@bot.command()
@commands.has_permissions(administrator=True)
async def restock(ctx, *, key_list):

    keys = [
        key.strip()
        for key in key_list.split(",")
        if key.strip()
    ]

    if not keys:
        await ctx.send("❌ You didn't provide any keys.")
        return

    added = add_keys(keys)
    stock_amount = get_stock()

    await ctx.send(
        f"✅ **Restocked!**\n\n"
        f"➕ Added: **{added}**\n"
        f"📦 Stock: **{stock_amount}**"
    )


# ---------------- VIEW KEYS ----------------

@bot.command()
@commands.has_permissions(administrator=True)
async def keys(ctx):

    all_keys = get_all_keys()

    if not all_keys:
        await ctx.send("📦 **Stock is empty.**")
        return

    text = "\n".join(
        f"`{key}`" for key in all_keys
    )

    # Discord message limit protection
    if len(text) > 1900:
        text = text[:1900] + "\n..."

    await ctx.send(
        f"🔐 **Unused Keys**\n\n{text}"
    )


# ---------------- REMOVE KEY ----------------

@bot.command()
@commands.has_permissions(administrator=True)
async def remove(ctx, *, key):

    removed = remove_key(key.strip())

    if removed:
        await ctx.send(
            f"🗑️ Removed `{key}` from the stock."
        )
    else:
        await ctx.send(
            f"❌ `{key}` wasn't found in stock."
        )


# ---------------- ADMIN ERROR ----------------

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "❌ You need **Administrator** permission to use that command."
        )

    elif isinstance(error, commands.CommandNotFound):
        return

    else:
        print(error)


# ---------------- START BOT ----------------

setup_database()

token = os.getenv("TOKEN")

if not token:
    raise RuntimeError(
        "TOKEN environment variable is missing!"
    )

bot.run(token)
