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
MAX_TOTAL_CLAIMS = 1  # Regular users can only ever claim ONE key


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


# ---------- Bot Setup ----------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

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
        pass
    except discord.HTTPException:
        pass


# ---------- Embed Builders ----------

def build_panel_embed(stock_count):
    """Build the main key distribution panel embed with live stock."""
    embed = discord.Embed(
        title="Key Distribution System",
        description=(
            "Welcome to the Key Vault. Click the button below to claim "
            "your key.\n\u200b"
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="Stock Available",
        value=f"**{stock_count}** keys in vault",
        inline=True
    )
    embed.add_field(
        name="Claim Limit",
        value=f"**{MAX_TOTAL_CLAIMS}** key per user",
        inline=True
    )
    embed.add_field(
        name="Delivery",
        value="Instant and private",
        inline=True
    )
    embed.add_field(
        name="How It Works",
        value=(
            "1. Press **Get Key** below\n"
            "2. Receive a random key privately\n"
            "3. Redeem it wherever you need\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="Important",
        value=(
            "• Each key can only be claimed **once**\n"
            "• Keys are distributed **randomly**\n"
            "• Only **you** can see your key"
        ),
        inline=False
    )
    embed.set_footer(text="Key Vault System • Good luck!")
    return embed


def build_key_embed(picked_key, stock_remaining, claim_number, max_claims, is_admin):
    """Build the private key delivery embed."""
    embed = discord.Embed(
        title="Key Claimed Successfully!",
        description=(
            "Here is your key — copy it with the button below:\n\n"
            f"`{picked_key}`\n\u200b"
        ),
        color=discord.Color.green()
    )
    embed.add_field(
        name="Stock Remaining",
        value=f"**{stock_remaining}** keys left",
        inline=True
    )
    embed.add_field(
        name="Your Claims",
        value=(
            f"**{claim_number}/{max_claims}** used"
            if not is_admin
            else "**Unlimited** (Admin)"
        ),
        inline=True
    )
    embed.add_field(
        name="Privacy",
        value="Only you can see this",
        inline=True
    )
    embed.add_field(
        name="Tip",
        value=(
            "Click the key text above to copy it, or tap and hold "
            "on mobile to copy."
        ),
        inline=False
    )
    embed.set_footer(text="Key Vault System • Redeem your key now!")
    return embed


# ---------- Key Button View ----------

class KeyButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Get Key", style=discord.ButtonStyle.primary, custom_id="get_key")
    async def get_key_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Get Key button press."""
        
        user_id = interaction.user.id
        is_admin = interaction.user.guild_permissions.administrator
        
        # Load keys
        keys = load_keys()
        
        if not keys:
            await interaction.response.send_message(
                "The vault is empty. Please wait for a restock.",
                ephemeral=True
            )
            return
        
        # Check claim limit (admins bypass)
        if not is_admin:
            user_info = get_user_info(user_id)
            if user_info["claims"] >= MAX_TOTAL_CLAIMS:
                await interaction.response.send_message(
                    "You have already claimed your key.\n"
                    "Each user can only claim **one** key.",
                    ephemeral=True
                )
                return
        
        # Pick a random key
        index = random.randrange(len(keys))
        picked_key = keys.pop(index)
        save_keys(keys)
        
        # Track claim (skip for admins)
        if not is_admin:
            update_user_claims(user_id)
            user_info = get_user_info(user_id)
            claim_number = user_info["claims"]
        else:
            claim_number = "∞"
        
        # Build the private key embed
        key_embed = build_key_embed(
            picked_key=picked_key,
            stock_remaining=len(keys),
            claim_number=claim_number,
            max_claims=MAX_TOTAL_CLAIMS,
            is_admin=is_admin
        )
        
        await interaction.response.send_message(embed=key_embed, ephemeral=True)
        
        # ---- Auto-update the panel embed's stock count ----
        try:
            if interaction.message and interaction.message.author.id == bot.user.id:
                updated_panel = build_panel_embed(len(keys))
                await interaction.message.edit(embed=updated_panel, view=self)
        except discord.HTTPException:
            pass  # Ignore edit failures (e.g., message deleted)


# ---------- SENDKEY COMMAND ----------

@bot.command(name="sendkey")
async def sendkey(ctx):
    """
    Send an embed with a Get Key button.
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    await delete_command_message(ctx)
    
    keys = load_keys()
    if not keys:
        await ctx.send("Cannot send key embed: The vault is empty. Use `.restock` first.")
        return
    
    embed = build_panel_embed(len(keys))
    view = KeyButtonView()
    await ctx.send(embed=embed, view=view)


# ---------- GENS COMMAND ----------

@bot.command(name="gens")
async def gens(ctx):
    """
    Check whether you have already claimed your key.
    """
    
    await delete_command_message(ctx)
    
    user_id = ctx.author.id
    is_admin = ctx.author.guild_permissions.administrator
    
    if is_admin:
        await ctx.send("You're an admin — unlimited claims.", ephemeral=True)
        return
    
    user_info = get_user_info(user_id)
    claims = user_info["claims"]
    
    if claims >= MAX_TOTAL_CLAIMS:
        await ctx.send(
            "You've already claimed your key.\n"
            f"Claims used: **{claims}/{MAX_TOTAL_CLAIMS}**",
            ephemeral=True
        )
    else:
        await ctx.send(
            "You have **1** claim available.\n"
            "Click the **Get Key** button to claim it!",
            ephemeral=True
        )


# ---------- LOGS COMMAND ----------

@bot.command(name="logs")
async def logs(ctx):
    """
    View all user claim activity.
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    await delete_command_message(ctx)
    
    user_data = get_all_user_data()
    
    if not user_data:
        await ctx.send("No user data yet.")
        return
    
    claimed_users = []
    guild = ctx.guild
    
    for user_id_str, data in user_data.items():
        user_id = int(user_id_str)
        claims = data["claims"]
        
        try:
            member = await guild.fetch_member(user_id)
            username = member.display_name if member else f"Unknown ({user_id})"
        except:
            username = f"Unknown ({user_id})"
        
        if claims > 0:
            claimed_users.append((username, claims))
    
    claimed_users.sort(key=lambda x: x[1], reverse=True)
    
    total_claims = sum(d["claims"] for d in user_data.values())
    
    embed = discord.Embed(
        title="Key Logs",
        description="Overview of all claim activity.\n\u200b",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Stock", value=f"**{len(load_keys())}** keys", inline=True)
    embed.add_field(name="Total Claims", value=f"**{total_claims}**", inline=True)
    embed.add_field(name="Users", value=f"**{len(user_data)}**", inline=True)
    
    if claimed_users:
        lines = [f"**{name}** — {count}" for name, count in claimed_users[:15]]
        if len(claimed_users) > 15:
            lines.append(f"*...and {len(claimed_users) - 15} more*")
        embed.add_field(name="Claimed By", value="\n".join(lines), inline=False)
    
    embed.set_footer(text="Key Vault System")
    await ctx.send(embed=embed)


# ---------- RESTOCK COMMAND ----------

@bot.command(name="restock")
async def restock(ctx):
    """
    Add keys to the vault via .txt file.
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    if not ctx.message.attachments:
        await ctx.send("Attach a `.txt` file with one key per line.")
        await delete_command_message(ctx)
        return
    
    attachment = ctx.message.attachments[0]
    
    if not attachment.filename.lower().endswith(".txt"):
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
    
    new_keys = [line.strip() for line in raw_text.splitlines() if line.strip()]
    
    if not new_keys:
        await ctx.send("That file had no keys in it.")
        await delete_command_message(ctx)
        return
    
    keys = load_keys()
    keys.extend(new_keys)
    save_keys(keys)
    
    await delete_command_message(ctx)
    await ctx.send(f"Added **{len(new_keys)}** keys. Total stock: **{len(keys)}**.")


# ---------- STOCK COMMAND ----------

@bot.command(name="stock")
async def stock(ctx):
    """
    Check how many keys are in the vault.
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    keys = load_keys()
    await delete_command_message(ctx)
    await ctx.send(f"**{len(keys)}** keys in vault.")


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
    await ctx.send("Stock cleared.")


# ---------- RESETUSER COMMAND ----------

@bot.command(name="resetuser")
async def resetuser(ctx, member: discord.Member = None):
    """
    Reset a user's claim so they can claim again.
    Admin only.
    """
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    if member is None:
        await ctx.send("Usage: `.resetuser @user`")
        await delete_command_message(ctx)
        return
    
    user_data = load_user_data()
    user_id_str = str(member.id)
    
    if user_id_str in user_data:
        user_data[user_id_str]["claims"] = 0
        user_data[user_id_str]["last_claim"] = 0
        save_user_data(user_data)
    
    await delete_command_message(ctx)
    await ctx.send(f"Reset claims for {member.mention}.")


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
