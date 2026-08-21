import json
import os
import random
import threading

import discord
from discord.ext import commands
from flask import Flask


# ---------- Configuration ----------

DATA_FILE = "keys.json"
PREFIX = "."
ALLOWED_CHANNEL_ID = 1539288424622850130


# ---------- Render Web Server ----------

app = Flask(__name__)


@app.route("/")
def home():
    return "Key Vault Bot is online!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# Start the web server in the background
threading.Thread(target=run_web, daemon=True).start()


# ---------- Storage Helpers ----------

def load_keys():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_keys(keys):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2)


# ---------- Bot Setup ----------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)


# ---------- Admin Check ----------

def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator

    return commands.check(predicate)


# ---------- Events ----------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("Key Vault Bot is online!")


# ---------- Global Checks ----------

@bot.check
async def block_dms(ctx):
    """Commands cannot be used in DMs."""

    if ctx.guild is None:
        await ctx.send(
            "Commands can't be used in DMs, use them in the server."
        )
        return False

    return True


@bot.check
async def restrict_channel(ctx):
    """
    Non-admins can only use commands in the allowed channel.
    Admins can use commands anywhere.
    """

    if ctx.author.guild_permissions.administrator:
        return True

    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send(
            f"Commands can only be used in <#{ALLOWED_CHANNEL_ID}>."
        )
        return False

    return True


# ---------- RESTOCK ----------

@bot.command(name="restock")
@is_admin()
async def restock(ctx):
    """
    Add keys to the vault.

    Usage:
    .restock

    Attach a .txt file with one key per line.
    """

    if not ctx.message.attachments:
        await ctx.send(
            "Attach a `.txt` file with the message, one key per line."
        )
        return

    attachment = ctx.message.attachments[0]

    if not attachment.filename.lower().endswith(".txt"):
        await ctx.send("Please attach a plain `.txt` file.")
        return

    raw_bytes = await attachment.read()

    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        await ctx.send(
            "Couldn't read that file. Make sure it is UTF-8 text."
        )
        return

    new_keys = [
        line.strip()
        for line in raw_text.splitlines()
        if line.strip()
    ]

    if not new_keys:
        await ctx.send(
            "That file didn't have any keys in it. "
            "Use one key per line."
        )
        return

    keys = load_keys()

    keys.extend(new_keys)

    save_keys(keys)

    await ctx.send(
        f"Added **{len(new_keys)}** keys from `{attachment.filename}`.\n"
        f"Total in stock: **{len(keys)}**."
    )


# ---------- VIEW ----------

@bot.command(name="view")
@is_admin()
async def view(ctx):
    """
    View every key currently in stock.

    Admin only.
    """

    keys = load_keys()

    if not keys:
        await ctx.send("The vault is empty.")
        return

    listing = "\n".join(
        f"`{key}`"
        for key in keys
    )

    # Discord message limit
    if len(listing) > 1900:

        with open(
            "stock_view.txt",
            "w",
            encoding="utf-8"
        ) as f:
            f.write("\n".join(keys))

        await ctx.send(
            f"**{len(keys)}** keys in stock. Sending them as a file:",
            file=discord.File("stock_view.txt")
        )

        os.remove("stock_view.txt")

    else:
        await ctx.send(
            f"**{len(keys)}** keys in stock:\n{listing}"
        )


# ---------- CLEAR ----------

@bot.command(name="clear")
@is_admin()
async def clear(ctx):
    """
    Delete every key from the vault.

    Admin only.
    """

    save_keys([])

    await ctx.send("Stock has been cleared.")


# ---------- STOCK ----------

@bot.command(name="stock")
async def stock(ctx):
    """
    Show how many keys are available.
    """

    keys = load_keys()

    await ctx.send(
        f"Stock: **{len(keys)}** keys remaining."
    )


# ---------- KEY ----------

@bot.command(name="key")
async def key(ctx):
    """
    Claim a random key.

    The key is removed from stock and sent through DM.
    """

    keys = load_keys()

    if not keys:
        await ctx.send("Sorry, we're out of stock.")
        return

    # Pick a random key
    index = random.randrange(len(keys))

    picked_key = keys.pop(index)

    # Save immediately so the key is removed
    save_keys(keys)

    try:

        await ctx.author.send(
            f" Your key:\n`{picked_key}`"
        )

        await ctx.send(
            f"{ctx.author.mention} check your DMs! "
            "Your key has been sent."
        )

    except discord.Forbidden:

        # Put the key back if the DM failed
        keys = load_keys()

        keys.append(picked_key)

        save_keys(keys)

        await ctx.send(
            f"{ctx.author.mention} I couldn't DM you.\n"
            "Please enable DMs and try again. "
            "Your key was returned to stock."
        )


# ---------- Admin Error Handling ----------

@restock.error
@view.error
@clear.error
async def admin_error(ctx, error):

    if isinstance(error, commands.CheckFailure):

        await ctx.send(
            " You need Administrator permission to do that."
        )

    else:

        await ctx.send(
            f" Error: {error}"
        )


# ---------- Run Bot ----------

if __name__ == "__main__":

    token = os.environ.get("DISCORD_TOKEN")

    # Optional local token.txt support
    if not token and os.path.exists("token.txt"):

        with open(
            "token.txt",
            "r",
            encoding="utf-8"
        ) as f:
            token = f.read().strip()

    if not token:

        raise SystemExit(
            "No bot token found.\n"
            "Set the DISCORD_TOKEN environment variable "
            "in Render."
        )

    bot.run(token)
