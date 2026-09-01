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
MAX_CLAIMS = 3
COOLDOWN_HOURS = 1
COOLDOWN_SECONDS = COOLDOWN_HOURS * 60 * 60  # 3600 seconds


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

def reset_user_claims(user_id):
    """Reset user's claims to 0."""
    user_data = load_user_data()
    user_id_str = str(user_id)
    
    if user_id_str in user_data:
        user_data[user_id_str]["claims"] = 0
        user_data[user_id_str]["last_claim"] = 0
        save_user_data(user_data)

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
    def __init__(self, stock_count, sendkey_message=None):
        super().__init__(timeout=None)
        self.stock_count = stock_count
        self.sendkey_message = sendkey_message
    
    @discord.ui.button(label="Get Key", style=discord.ButtonStyle.primary, custom_id="get_key")
    async def get_key_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Get Key button press."""
        
        user_id = interaction.user.id
        is_admin = interaction.user.guild_permissions.administrator
        
        # Load keys
        keys = load_keys()
        
        if not keys:
            await interaction.response.send_message("The vault is empty. Please wait for a restock.", ephemeral=True)
            return
        
        # Check user's claim status (skip for admins)
        if not is_admin:
            user_info = get_user_info(user_id)
            claims = user_info["claims"]
            last_claim = user_info["last_claim"]
            
            # Check if user has reached max claims
            if claims >= MAX_CLAIMS:
                # Check if cooldown has passed
                time_since_last = time.time() - last_claim
                if time_since_last < COOLDOWN_SECONDS:
                    remaining = int(COOLDOWN_SECONDS - time_since_last)
                    hours = remaining // 3600
                    minutes = (remaining % 3600) // 60
                    seconds = remaining % 60
                    
                    await interaction.response.send_message(
                        f"You have reached the maximum of {MAX_CLAIMS} claims. "
                        f"Cooldown remaining: {hours}h {minutes}m {seconds}s",
                        ephemeral=True
                    )
                    return
                else:
                    # Cooldown passed, reset claims
                    reset_user_claims(user_id)
        
        # Pick a random key
        index = random.randrange(len(keys))
        picked_key = keys.pop(index)
        
        # Save immediately so the key is removed
        save_keys(keys)
        
        # Update user claims (skip for admins)
        if not is_admin:
            update_user_claims(user_id)
            user_info = get_user_info(user_id)
            claims_remaining = MAX_CLAIMS - user_info["claims"]
        else:
            claims_remaining = "Unlimited (Admin)"
        
        # Update the sendkey embed with new stock count
        if self.sendkey_message:
            try:
                # Get current embed
                old_embed = self.sendkey_message.embeds[0]
                
                # Create updated embed
                new_embed = discord.Embed(
                    title=old_embed.title,
                    description=old_embed.description,
                    color=old_embed.color
                )
                
                # Update fields with new stock count
                for field in old_embed.fields:
                    if field.name == "Available Keys":
                        new_embed.add_field(
                            name=field.name,
                            value=f"{len(keys)} keys currently in stock",
                            inline=field.inline
                        )
                    else:
                        new_embed.add_field(
                            name=field.name,
                            value=field.value,
                            inline=field.inline
                        )
                
                new_embed.timestamp = old_embed.timestamp
                new_embed.set_footer(text=old_embed.footer.text)
                
                # Edit the sendkey message
                await self.sendkey_message.edit(embed=new_embed)
            except:
                pass
        
        # Create detailed embed for the key (ephemeral - only visible to the user)
        embed = discord.Embed(
            title="Key Generated",
            description=f"**Your Key:**\n`{picked_key}`",
            color=discord.Color.dark_blue()
        )
        
        # Add detailed fields
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
        
        # Add claims info (skip for admins)
        if not is_admin:
            embed.add_field(
                name="Your Claims",
                value=f"{user_info['claims']} of {MAX_CLAIMS} used",
                inline=True
            )
            embed.add_field(
                name="Claims Remaining",
                value=f"{claims_remaining} claims left",
                inline=True
            )
        else:
            embed.add_field(
                name="Admin Status",
                value="Unlimited claims (Admin)",
                inline=True
            )
        
        # Add timestamp
        embed.timestamp = interaction.created_at
        
        # Add footer
        embed.set_footer(text="Key Vault System")
        
        # Send the key as ephemeral (only visible to the user who clicked)
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
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    # Delete the command message
    await delete_command_message(ctx)
    
    # Check if there are keys available
    keys = load_keys()
    if not keys:
        await ctx.send("Cannot send key embed: The vault is empty. Use .restock to add keys first.")
        return
    
    # Create detailed embed
    embed = discord.Embed(
        title="Key Distribution System",
        description="Click the button below to claim a key from the vault.",
        color=discord.Color.blue()
    )
    
    # Add detailed fields
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
        name="Claim Limits",
        value=f"Each user can claim up to {MAX_CLAIMS} keys per hour.",
        inline=False
    )
    embed.add_field(
        name="Important Notice",
        value="Each key can only be claimed once. Keys are distributed randomly.",
        inline=False
    )
    
    # Add timestamp
    embed.timestamp = ctx.message.created_at
    
    # Add footer
    embed.set_footer(text="Key Vault System")
    
    # Create view with button and pass the message reference
    view = KeyButtonView(len(keys))
    
    # Send the embed with button
    message = await ctx.send(embed=embed, view=view)
    
    # Update the view with the message reference
    view.sendkey_message = message


# ---------- GENS COMMAND ----------

@bot.command(name="gens")
async def gens(ctx):
    """
    Check how many keys you have claimed and how many are remaining.
    
    Usage:
    .gens
    """
    
    # Delete the command message
    await delete_command_message(ctx)
    
    user_id = ctx.author.id
    is_admin = ctx.author.guild_permissions.administrator
    
    if is_admin:
        await ctx.send("You are an admin. You have unlimited claims.", ephemeral=True)
        return
    
    user_info = get_user_info(user_id)
    claims = user_info["claims"]
    last_claim = user_info["last_claim"]
    
    # Calculate remaining claims
    if claims >= MAX_CLAIMS:
        # Check if cooldown has passed
        time_since_last = time.time() - last_claim
        if time_since_last < COOLDOWN_SECONDS:
            remaining_time = int(COOLDOWN_SECONDS - time_since_last)
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            seconds = remaining_time % 60
            
            await ctx.send(
                f"Your Claims: {claims} of {MAX_CLAIMS} used\n"
                f"Status: Cooldown active\n"
                f"Time remaining: {hours}h {minutes}m {seconds}s",
                ephemeral=True
            )
            return
        else:
            # Cooldown passed, reset claims
            reset_user_claims(user_id)
            claims = 0
    
    claims_remaining = MAX_CLAIMS - claims
    
    await ctx.send(
        f"Your Claims: {claims} of {MAX_CLAIMS} used\n"
        f"Claims Remaining: {claims_remaining}\n"
        f"Status: Ready to claim",
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
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    # Delete the command message
    await delete_command_message(ctx)
    
    # Get all user data
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
    
    # Separate users into categories
    active_users = []
    cooldown_users = []
    
    # Get guild for member info
    guild = ctx.guild
    
    for user_id_str, data in user_data.items():
        user_id = int(user_id_str)
        claims = data["claims"]
        last_claim = data["last_claim"]
        
        # Get user display name
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
        
        # Calculate cooldown status
        if claims >= MAX_CLAIMS and not is_admin:
            time_since_last = time.time() - last_claim
            if time_since_last < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - time_since_last)
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                seconds = remaining % 60
                cooldown_status = f"{hours}h {minutes}m {seconds}s"
                cooldown_users.append({
                    "id": user_id,
                    "name": username,
                    "claims": claims,
                    "cooldown": cooldown_status,
                    "is_admin": is_admin
                })
                continue
        
        # Active users (can claim or admins)
        if claims > 0 or is_admin:
            active_users.append({
                "id": user_id,
                "name": username,
                "claims": claims,
                "max_claims": MAX_CLAIMS if not is_admin else "Unlimited",
                "remaining": MAX_CLAIMS - claims if not is_admin else "Unlimited",
                "is_admin": is_admin
            })
    
    # Sort users by claims (highest first)
    active_users.sort(key=lambda x: x["claims"] if isinstance(x["claims"], int) else 999, reverse=True)
    cooldown_users.sort(key=lambda x: x["claims"], reverse=True)
    
    # Create embeds
    embeds = []
    
    # Summary embed
    summary_embed = discord.Embed(
        title="Logs - Key Vault System",
        description="Summary of all user activity",
        color=discord.Color.blue()
    )
    
    total_users = len(user_data)
    total_claims = sum(data["claims"] for data in user_data.values())
    
    summary_embed.add_field(
        name="Total Users",
        value=f"{total_users}",
        inline=True
    )
    summary_embed.add_field(
        name="Total Claims",
        value=f"{total_claims}",
        inline=True
    )
    summary_embed.add_field(
        name="Active Users",
        value=f"{len(active_users)}",
        inline=True
    )
    summary_embed.add_field(
        name="Cooldown Users",
        value=f"{len(cooldown_users)}",
        inline=True
    )
    summary_embed.add_field(
        name="Stock Available",
        value=f"{len(load_keys())} keys",
        inline=True
    )
    summary_embed.add_field(
        name="Max Claims Per User",
        value=f"{MAX_CLAIMS} per hour",
        inline=True
    )
    
    summary_embed.set_footer(text="Key Vault System")
    summary_embed.timestamp = ctx.message.created_at
    embeds.append(summary_embed)
    
    # Active users embed
    if active_users:
        active_embed = discord.Embed(
            title="Active Users",
            description="Users who have claimed keys and are ready to claim more",
            color=discord.Color.green()
        )
        
        active_list = ""
        for user in active_users[:25]:  # Limit to 25 per embed
            admin_tag = " [Admin]" if user["is_admin"] else ""
            active_list += f"**{user['name']}**{admin_tag}\n"
            if user["is_admin"]:
                active_list += f"  Claims: Unlimited\n\n"
            else:
                active_list += f"  Claims: {user['claims']} of {MAX_CLAIMS}\n"
                active_list += f"  Remaining: {user['remaining']} claims\n\n"
        
        if len(active_users) > 25:
            active_list += f"\n*... and {len(active_users) - 25} more users*"
        
        active_embed.description = active_list
        active_embed.set_footer(text="Key Vault System")
        active_embed.timestamp = ctx.message.created_at
        embeds.append(active_embed)
    else:
        active_embed = discord.Embed(
            title="Active Users",
            description="No active users found.",
            color=discord.Color.green()
        )
        active_embed.set_footer(text="Key Vault System")
        active_embed.timestamp = ctx.message.created_at
        embeds.append(active_embed)
    
    # Cooldown users embed
    if cooldown_users:
        cooldown_embed = discord.Embed(
            title="Cooldown Users",
            description="Users currently on cooldown",
            color=discord.Color.red()
        )
        
        cooldown_list = ""
        for user in cooldown_users[:25]:  # Limit to 25 per embed
            admin_tag = " [Admin]" if user["is_admin"] else ""
            cooldown_list += f"**{user['name']}**{admin_tag}\n"
            cooldown_list += f"  Claims: {user['claims']} of {MAX_CLAIMS}\n"
            cooldown_list += f"  Cooldown: {user['cooldown']}\n\n"
        
        if len(cooldown_users) > 25:
            cooldown_list += f"\n*... and {len(cooldown_users) - 25} more users*"
        
        cooldown_embed.description = cooldown_list
        cooldown_embed.set_footer(text="Key Vault System")
        cooldown_embed.timestamp = ctx.message.created_at
        embeds.append(cooldown_embed)
    else:
        cooldown_embed = discord.Embed(
            title="Cooldown Users",
            description="No users currently on cooldown.",
            color=discord.Color.green()
        )
        cooldown_embed.set_footer(text="Key Vault System")
        cooldown_embed.timestamp = ctx.message.created_at
        embeds.append(cooldown_embed)
    
    # Send all embeds
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
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
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
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
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
    
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need Administrator permission to use this command.")
        await delete_command_message(ctx)
        return
    
    save_keys([])
    
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
