import json
import os
import random
import threading
import asyncio

import discord
from discord.ext import commands
from discord.ui import Button, View
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

# Store the last key message ID to delete it later
last_key_message_id = None


# ---------- Events ----------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("Key Bot is online!")


# ---------- Command Message Deletion Helper ----------

async def delete_command_message(ctx):
    """Delete the user's command message only."""
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Bot doesn't have permission to delete messages
    except discord.HTTPException:
        pass  # Other error occurred


# ---------- Global Check - Block Non-Admins ----------

@bot.check
async def admin_only(ctx):
    """
    Only administrators can use commands.
    Non-admins get blocked silently.
    """
    if not ctx.author.guild_permissions.administrator:
        # Delete the command message without sending a reply
        try:
            await ctx.message.delete()
        except:
            pass
        return False
    return True


# ---------- Key Button View ----------

class KeyButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Get Key", style=discord.ButtonStyle.primary, custom_id="get_key")
    async def get_key_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Get Key button press."""
        global last_key_message_id
        
        # Check if user is admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need Administrator permission to use this button.", ephemeral=True)
            return
        
        # Load keys
        keys = load_keys()
        
        if not keys:
            await interaction.response.send_message("The vault is empty. Use `.restock` to add keys.", ephemeral=True)
            return
        
        # Pick a random key
        index = random.randrange(len(keys))
        picked_key = keys.pop(index)
        
        # Save immediately so the key is removed
        save_keys(keys)
        
        # Delete the previous key message if it exists
        if last_key_message_id:
            try:
                prev_msg = await interaction.channel.fetch_message(last_key_message_id)
                await prev_msg.delete()
            except:
                pass
        
        # Delete the button press message
        try:
            await interaction.message.delete()
        except:
            pass
        
        # Create embed for the key
        embed = discord.Embed(
            title="🔑 Key Generated",
            description=f"Here's your key:\n`{picked_key}`",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Remaining stock: {len(keys)} keys")
        
        # Send the new key with the button again
        view = KeyButtonView()
        msg = await interaction.channel.send(embed=embed, view=view)
        
        # Store the new message ID
        last_key_message_id = msg.id
        
        await interaction.response.send_message("Key sent successfully!", ephemeral=True)


# ---------- SENDKEY COMMAND ----------

@bot.command(name="sendkey")
async def sendkey(ctx):
    """
    Send an embed with a Get Key button.
    
    Usage:
    .sendkey
    
    Admin only.
    """
    
    # Delete the command message
    await delete_command_message(ctx)
    
    # Check if there are keys available
    keys = load_keys()
    if not keys:
        await ctx.send("Cannot send key embed: The vault is empty. Use `.restock` to add keys first.")
        return
    
    # Create embed
    embed = discord.Embed(
        title="🔑 Get Your Key",
        description="Click the button below to get a key.",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Stock available: {len(keys)} keys")
    
    # Create view with button
    view = KeyButtonView()
    
    # Send the embed with button
    await ctx.send(embed=embed, view=view)


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
    
    # Check for attachment first
    if not ctx.message.attachments:
        await ctx.send("Attach a `.txt` file with the message, one key per line.")
        await delete_command_message(ctx)
        return
    
    # Get attachment info
    attachment = ctx.message.attachments[0]
    filename = attachment.filename
    
    if not filename.lower().endswith(".txt"):
        await ctx.send("Please attach a plain `.txt` file.")
        await delete_command_message(ctx)
        return
    
    # Read the file
    raw_bytes = await attachment.read()
    
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        await ctx.send("Couldn't read that file. Make sure it is UTF-8 text.")
        await delete_command_message(ctx)
        return
    
    new_keys = [
        line.strip()
        for line in raw_text.splitlines()
        if line.strip()
    ]
    
    if not new_keys:
        await ctx.send("That file didn't have any keys in it. Use one key per line.")
        await delete_command_message(ctx)
        return
    
    # Add keys to stock
    keys = load_keys()
    keys.extend(new_keys)
    save_keys(keys)
    
    # Delete the command message after successful restock
    await delete_command_message(ctx)
    
    await ctx.send(
        f"Added {len(new_keys)} keys from `{filename}`.\n"
        f"Total in stock: {len(keys)}."
    )


# ---------- STOCK COMMAND ----------

@bot.command(name="stock")
async def stock(ctx):
    """
    Check how many keys are in the vault.
    
    Usage:
    .stock
    Admin only.
    """
    
    keys = load_keys()
    count = len(keys)
    
    # Delete the command message
    await delete_command_message(ctx)
    
    # Send stock count
    await ctx.send(f"{count} keys in vault")


# ---------- CLEARSTOCK COMMAND ----------

@bot.command(name="clearstock")
async def clearstock(ctx):
    """
    Delete every key from the vault.
    
    Admin only.
    """
    
    global last_key_message_id
    
    save_keys([])
    
    # Delete the previous key message if it exists
    if last_key_message_id:
        try:
            prev_msg = await ctx.channel.fetch_message(last_key_message_id)
            await prev_msg.delete()
        except:
            pass
        last_key_message_id = None
    
    # Delete the command message
    await delete_command_message(ctx)
    
    await ctx.send("Stock has been cleared.")


# ---------- Error Handling ----------

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        # Already handled by the global check
        pass
    elif isinstance(error, commands.CommandNotFound):
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
