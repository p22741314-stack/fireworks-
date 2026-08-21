"""
Key Vault Discord Bot
----------------------
Give out keys from a single storage pool:
- Admins restock by attaching a .txt file (one key per line)
- Anyone can claim a key with .getkey (removed from storage, sent via DM)
- Anyone can view current stock with .stock

Storage is a simple JSON file (keys.json) so it persists across restarts.
No external database needed.

Setup:
1. pip install -r requirements.txt
2. Create a bot at https://discord.com/developers/applications
   - Enable "Message Content Intent" under Bot settings
3. Put your bot token in a file called token.txt (or set DISCORD_TOKEN env var)
4. Run: python bot.py
"""

import json
import os
import discord
from discord.ext import commands

DATA_FILE = "keys.json"
PREFIX = "."

# ---------- Storage helpers ----------

def load_keys():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_keys(keys):
    with open(DATA_FILE, "w") as f:
        json.dump(keys, f, indent=2)

# ---------- Bot setup ----------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


def is_admin():
    """Restrict a command to users with Administrator permission."""
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")


# ---------- Commands ----------

@bot.command(name="restock")
@is_admin()
async def restock(ctx):
    """
    Add keys to the vault by attaching a .txt file (one key per line).
    Usage: .restock   (with a .txt file attached to the message)
    """
    if not ctx.message.attachments:
        await ctx.send("Attach a .txt file with the message, one key per line.")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith(".txt"):
        await ctx.send("Please attach a plain .txt file.")
        return

    raw_bytes = await attachment.read()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        await ctx.send("Couldn't read that file, make sure it's plain UTF-8 text.")
        return

    new_keys = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not new_keys:
        await ctx.send("That file didn't have any keys in it (one per line).")
        return

    keys = load_keys()
    keys.extend(new_keys)
    save_keys(keys)

    await ctx.send(f"Added {len(new_keys)} key(s) from {attachment.filename}. "
                    f"Total in stock: {len(keys)}.")


@bot.command(name="stock")
async def stock(ctx):
    """
    View how many keys are currently in stock.
    Usage: .stock
    """
    keys = load_keys()
    await ctx.send(f"Stock: {len(keys)} key(s) remaining.")


@bot.command(name="getkey")
async def getkey(ctx):
    """
    Claim a key. It is removed from storage and DMed to you.
    Usage: .getkey
    """
    keys = load_keys()

    if not keys:
        await ctx.send("Sorry, out of stock.")
        return

    key = keys.pop(0)  # take the first available key
    save_keys(keys)

    try:
        await ctx.author.send(f"Here is your key:\n```{key}```")
        await ctx.send(f"{ctx.author.mention} Check your DMs, your key has been sent.")
    except discord.Forbidden:
        # If DMs are closed, put the key back so it isn't lost
        keys = load_keys()
        keys.insert(0, key)
        save_keys(keys)
        await ctx.send(f"{ctx.author.mention} I couldn't DM you (check your privacy settings). "
                        f"Your key was not taken from stock, try again after enabling DMs.")


@restock.error
async def admin_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need Administrator permission to do that.")
    else:
        await ctx.send(f"Error: {error}")


# ---------- Run ----------

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token and os.path.exists("token.txt"):
        with open("token.txt", "r") as f:
            token = f.read().strip()

    if not token:
        raise SystemExit(
            "No bot token found. Set the DISCORD_TOKEN environment variable "
            "or create a token.txt file containing your bot token."
        )

    bot.run(token)
