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


# ---------- Render Web Server ----------

app = Flask(__name__)

@app.route("/")
def home():
    return "Key Bot is online!"

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


# ---------- Events ----------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("Key Bot is online!")


# ---------- RESTOCK COMMAND ----------

@bot.command(name="restock")
async def restock(ctx):
    """
    Add keys to the vault.
    
    Usage:
    .restock
    
    Attach a .txt file with one key per line.
    Admin only.
    """
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        return
    
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
        await ctx.send("Couldn't read that file. Make sure it is UTF-8 text.")
        return
    
    new_keys = [
        line.strip()
        for line in raw_text.splitlines()
        if line.strip()
    ]
    
    if not new_keys:
        await ctx.send("That file didn't have any keys in it. Use one key per line.")
        return
    
    keys = load_keys()
    keys.extend(new_keys)
    save_keys(keys)
    
    await ctx.send(
        f"Added {len(new_keys)} keys from {attachment.filename}.\n"
        f"Total in stock: {len(keys)}."
    )


# ---------- KEY COMMAND ----------

@bot.command(name="key")
async def key(ctx):
    """
    Display a random key from stock.
    
    The key is removed from stock and shown publicly.
    Admin only.
    """
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        return
    
    keys = load_keys()
    
    if not keys:
        await ctx.send("The vault is empty. Use .restock to add keys.")
        return
    
    # Pick a random key
    index = random.randrange(len(keys))
    picked_key = keys.pop(index)
    
    # Save immediately so the key is removed
    save_keys(keys)
    
    # Send the key publicly
    await ctx.send(
        f"Key: {picked_key}\n"
        f"Remaining stock: {len(keys)}"
    )


# ---------- CLEARSTOCK COMMAND ----------

@bot.command(name="clearstock")
async def clearstock(ctx):
    """
    Delete every key from the vault.
    
    Admin only.
    """
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        return
    
    save_keys([])
    
    await ctx.send("Stock has been cleared.")


# ---------- Error Handling ----------

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # Ignore unknown commands
        pass
    else:
        await ctx.send(f"Error: {error}")


# ---------- Run Bot ----------

if __name__ == "__main__":
    
    token = os.environ.get("DISCORD_TOKEN")
    
    # Optional local token.txt support
    if not token and os.path.exists("token.txt"):
        with open("token.txt", "r", encoding="utf-8") as f:
            token = f.read().strip()
    
    if not token:
        raise SystemExit(
            "No bot token found.\n"
            "Set the DISCORD_TOKEN environment variable in Render."
        )
    
    bot.run(token)
