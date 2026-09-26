import json
import os
import random
import threading
import asyncio
import time

import discord
from discord.ext import commands
from discord.ui import Button, View
from flask import Flask


# ---------- Configuration ----------

DATA_FILE = "keys.json"
BLACKLIST_FILE = "blacklist.json"
PREFIX = "."
MAX_TOTAL_CLAIMS = 1  # Each user can only ever claim ONE key


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


# ---------- User Tracking ----------

USER_DATA_FILE = "user_data.json"

def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        return {}

    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save_user_data(user_data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=2)

def get_user_info(user_id):
    """Get user's claim count and last claim time."""
    user_data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "claims": 0,
            "last_claim": 0
        }
        save_user_data(user_data)
    
    return user_data[user_id_str]

def update_user_claims(user_id):
    """Update user's claim count and last claim time."""
    user_data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "claims": 0,
            "last_claim": 0
        }
    
    user_data[user_id_str]["claims"] += 1
    user_data[user_id_str]["last_claim"] = time.time()
    save_user_data(user_data)
    
    return user_data[user_id_str]

def get_all_user_data():
    """Get all user data."""
    return load_user_data()


# ---------- Helper to get display name ----------

async def get_user_display_name(guild, user_id):
    """Get a user's display name from the guild."""
    try:
        member = await guild.fetch_member(user_id)
        if member:
            return member.display_name
    except:
        pass
    return f"User {user_id}"


# ---------- Bot Setup ----------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required to fetch member info

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)


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


# ---------- Key Button View ----------

class KeyButtonView(View):
    def __init__(self, stock_count):
        super().__init__(timeout=None)
        self.stock_count = stock_count
    
    @discord.ui.button(label="Get Key", style=discord.ButtonStyle.primary, custom_id="get_key")
    async def get_key_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Get Key button press."""
        
        user_id = interaction.user.id
        
        # Load keys
        keys = load_keys()
        
        if not keys:
            await interaction.response.send_message(
                "The vault is empty. Please wait for a restock.",
                ephemeral=True
            )
            return
        
        # Check if user has already claimed their one key
        user_info = get_user_info(user_id)
        claims = user_info["claims"]
        
        if claims >= MAX_TOTAL_CLAIMS:
            await interaction.response.send_message(
                "You have already claimed your key. Each user can only claim **one** key.",
                ephemeral=True
            )
            return
        
        # Pick a random key
        index = random.randrange(len(keys))
        picked_key = keys.pop(index)
        
        # Save immediately so the key is removed
        save_keys(keys)
        
        # Update user claim count
        update_user_claims(user_id)
        user_info = get_user_info(user_id)
        
        # Create detailed embed for the key (ephemeral - only visible to the user)
        embed = discord.Embed(
            title="Key Generated",
            description=f"**Your Key:**\n`{picked_key}`",
            color=discord.Color.dark_blue()
        )
        
        embed.add_field(
            name="Status",
            value="Key has been claimed successfully.",
            inline=False
        )
        embed.add_field(
            name="Remaining Stock",
            value=f"{len(keys)} keys available",
            inline=True
        )
        embed.add_field(
            name="Claimed By",
            value=interaction.user.mention,
            inline=True
        )
        embed.add_field(
            name="Claim Limit",
            value="You have now used your **1** allowed claim.",
            inline=False
        )
        
        embed.timestamp = interaction.created_at
        embed.set_footer(text="Key Vault System")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------- SENDKEY COMMAND ----------

@bot.command(name="sendkey")
async def sendkey(ctx):
    """
    Send an embed with a Get Key button.
    
    Usage:
    .sendkey
    
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    await delete_command_message(ctx)
    
    keys = load_keys()
    if not keys:
        await ctx.send("Cannot send key embed: The vault is empty. Use .restock to add keys first.")
        return
    
    embed = discord.Embed(
        title="Key Distribution System",
        description="Click the button below to claim a key from the vault.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Available Keys",
        value=f"{len(keys)} keys currently in stock",
        inline=True
    )
    embed.add_field(
        name="How to Claim",
        value="Press the 'Get Key' button below to receive a random key.",
        inline=True
    )
    embed.add_field(
        name="Claim Limit",
        value="Each user can only claim **1 key total**.",
        inline=False
    )
    embed.add_field(
        name="Important Notice",
        value="Each key can only be claimed once. Keys are distributed randomly.",
        inline=False
    )
    
    embed.timestamp = ctx.message.created_at
    embed.set_footer(text="Key Vault System")
    
    view = KeyButtonView(len(keys))
    await ctx.send(embed=embed, view=view)


# ---------- GENS COMMAND ----------

@bot.command(name="gens")
async def gens(ctx):
    """
    Check whether you have already claimed your key.
    
    Usage:
    .gens
    """
    
    await delete_command_message(ctx)
    
    user_id = ctx.author.id
    user_info = get_user_info(user_id)
    claims = user_info["claims"]
    
    if claims >= MAX_TOTAL_CLAIMS:
        await ctx.send(
            "You have already claimed your key.\n"
            "Each user can only claim **1** key.",
            ephemeral=True
        )
    else:
        await ctx.send(
            "You have not claimed a key yet.\n"
            "You have **1** claim available.",
            ephemeral=True
        )


# ---------- LOGS COMMAND ----------

@bot.command(name="logs")
async def logs(ctx):
    """
    View detailed logs of all user claims and status.
    
    Usage:
    .logs
    
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    await delete_command_message(ctx)
    
    user_data = get_all_user_data()
    
    if not user_data:
        embed = discord.Embed(
            title="Logs - Key Vault System",
            description="No user data available yet.",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Key Vault System")
        embed.timestamp = ctx.message.created_at
        await ctx.send(embed=embed)
        return
    
    claimed_users = []
    unclaimed_users = []
    
    guild = ctx.guild
    
    for user_id_str, data in user_data.items():
        user_id = int(user_id_str)
        claims = data["claims"]
        
        try:
            member = await guild.fetch_member(user_id)
            if member:
                username = member.display_name
                is_admin = member.guild_permissions.administrator
            else:
                username = f"Unknown User ({user_id})"
                is_admin = False
        except:
            username = f"Unknown User ({user_id})"
            is_admin = False
        
        entry = {
            "id": user_id,
            "name": username,
            "claims": claims,
            "is_admin": is_admin
        }
        
        if claims >= MAX_TOTAL_CLAIMS:
            claimed_users.append(entry)
        elif claims > 0:
            unclaimed_users.append(entry)
    
    claimed_users.sort(key=lambda x: x["claims"], reverse=True)
    unclaimed_users.sort(key=lambda x: x["claims"], reverse=True)
    
    embeds = []
    
    # Summary embed
    summary_embed = discord.Embed(
        title="Logs - Key Vault System",
        description="Summary of all user activity",
        color=discord.Color.blue()
    )
    
    total_users = len(user_data)
    total_claims = sum(data["claims"] for data in user_data.values())
    
    summary_embed.add_field(name="Total Users", value=f"{total_users}", inline=True)
    summary_embed.add_field(name="Total Claims", value=f"{total_claims}", inline=True)
    summary_embed.add_field(name="Users Who Claimed", value=f"{len(claimed_users)}", inline=True)
    summary_embed.add_field(name="Stock Available", value=f"{len(load_keys())} keys", inline=True)
    summary_embed.add_field(name="Max Claims Per User", value=f"{MAX_TOTAL_CLAIMS} (one-time)", inline=True)
    summary_embed.set_footer(text="Key Vault System")
    summary_embed.timestamp = ctx.message.created_at
    embeds.append(summary_embed)
    
    # Claimed users embed
    if claimed_users:
        claimed_embed = discord.Embed(
            title="Users Who Have Claimed",
            description="These users have used their one allowed claim.",
            color=discord.Color.red()
        )
        
        claimed_list = ""
        for user in claimed_users[:25]:
            admin_tag = " [Admin]" if user["is_admin"] else ""
            claimed_list += f"**{user['name']}**{admin_tag}\n"
            claimed_list += f"  Claims: {user['claims']}\n\n"
        
        if len(claimed_users) > 25:
            claimed_list += f"\n*... and {len(claimed_users) - 25} more users*"
        
        claimed_embed.description = claimed_list
        claimed_embed.set_footer(text="Key Vault System")
        claimed_embed.timestamp = ctx.message.created_at
        embeds.append(claimed_embed)
    else:
        claimed_embed = discord.Embed(
            title="Users Who Have Claimed",
            description="No users have claimed a key yet.",
            color=discord.Color.green()
        )
        claimed_embed.set_footer(text="Key Vault System")
        claimed_embed.timestamp = ctx.message.created_at
        embeds.append(claimed_embed)
    
    # Unclaimed users embed
    if unclaimed_users:
        unclaimed_embed = discord.Embed(
            title="Partial Claim Records",
            description="Users with an unexpected partial claim count.",
            color=discord.Color.gold()
        )
        
        unclaimed_list = ""
        for user in unclaimed_users[:25]:
            unclaimed_list += f"**{user['name']}**\n"
            unclaimed_list += f"  Claims: {user['claims']}\n\n"
        
        if len(unclaimed_users) > 25:
            unclaimed_list += f"\n*... and {len(unclaimed_users) - 25} more users*"
        
        unclaimed_embed.description = unclaimed_list
        unclaimed_embed.set_footer(text="Key Vault System")
        unclaimed_embed.timestamp = ctx.message.created_at
        embeds.append(unclaimed_embed)
    
    for embed in embeds:
        await ctx.send(embed=embed)


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
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    if not ctx.message.attachments:
        await ctx.send("Attach a `.txt` file with the message, one key per line.")
        await delete_command_message(ctx)
        return
    
    attachment = ctx.message.attachments[0]
    filename = attachment.filename
    
    if not filename.lower().endswith(".txt"):
        await ctx.send("Please attach a plain `.txt` file.")
        await delete_command_message(ctx)
        return
    
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
    
    keys = load_keys()
    keys.extend(new_keys)
    save_keys(keys)
    
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
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    keys = load_keys()
    count = len(keys)
    
    await delete_command_message(ctx)
    await ctx.send(f"{count} keys in vault")


# ---------- CLEARSTOCK COMMAND ----------

@bot.command(name="clearstock")
async def clearstock(ctx):
    """
    Delete every key from the vault.
    
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    save_keys([])
    await delete_command_message(ctx)
    await ctx.send("Stock has been cleared.")


# ---------- RESETUSER COMMAND (bonus, useful for testing) ----------

@bot.command(name="resetuser")
async def resetuser(ctx, member: discord.Member = None):
    """
    Reset a user's claim so they can claim again.
    
    Usage:
    .resetuser @user
    
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    if member is None:
        await ctx.send("Please mention a user: `.resetuser @user`")
        await delete_command_message(ctx)
        return
    
    user_data = load_user_data()
    user_id_str = str(member.id)
    
    if user_id_str in user_data:
        user_data[user_id_str]["claims"] = 0
        user_data[user_id_str]["last_claim"] = 0
        save_user_data(user_data)
    
    await delete_command_message(ctx)
    await ctx.send(f"Reset claim data for {member.mention}.")


# ---------- Error Handling ----------

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"Error: {error}")


# ---------- Run Bot ----------

if __name__ == "__main__":
    
    token = os.environ.get("DISCORD_TOKEN")
    
    if not token and os.path.exists("token.txt"):
        with open("token.txt", "r", encoding="utf-8") as f:
            token = f.read().strip()
    
    if not token:
        raise SystemExit(
            "No bot token found.\n"
            "Set the DISCORD_TOKEN environment variable in Render."
        )
    
    bot.run(token)
