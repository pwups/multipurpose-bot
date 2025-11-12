import discord
from discord.ext import commands
import os
from discord.ui import View, Button
from dotenv import load_dotenv
from datetime import date, timedelta, datetime
import json
import ast
import re
import operator

load_dotenv()

def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("ERROR: config.json not found. Please create it from the template.")
        exit(1)
    except json.JSONDecodeError:
        print("ERROR: config.json is not valid JSON.")
        exit(1)

config = load_config()

GUILD_ID = config.get("GUILD_ID")
LAUGHBOARD_CHANNEL_ID = config.get("LAUGHBOARD_CHANNEL_ID")
TARGET_EMOJI = config.get("TARGET_EMOJI", "😆")
THRESHOLD = config.get("THRESHOLD", 5)
CHANNEL_ID = config.get("CHANNEL_ID")
ROLE_ID = config.get("ROLE_ID")
VANITY_CHANNEL_ID = config.get("VANITY_CHANNEL_ID")
VANITY_STRING = os.getenv('VANITY_STRING', '/kaede')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found in environment variables.")
    print("Please create a .env file with your DISCORD_TOKEN.")
    exit(1)

STREAKS_FILE = "streaks.json"

def load_streaks():
    try:
        with open(STREAKS_FILE, "r") as f:
            data = json.load(f)
            highest = data.get("highest", {})
            current = data.get("current", {})
            
            for user_id in current:
                if isinstance(current[user_id][1], str):
                    try:
                        current[user_id][1] = datetime.fromisoformat(current[user_id][1]).date()
                    except (ValueError, AttributeError):
                        current[user_id][1] = date.today()
            
            return highest, current
    except FileNotFoundError:
        return {}, {}
    except json.JSONDecodeError:
        print(f"WARNING: {STREAKS_FILE} is corrupted. Starting with empty streaks.")
        return {}, {}

def save_streaks(highest_hash, current_hash):
    try:
        current_serializable = {}
        for user_id, (count, streak_date) in current_hash.items():
            if isinstance(streak_date, date):
                current_serializable[user_id] = [count, streak_date.isoformat()]
            else:
                current_serializable[user_id] = [count, str(streak_date)]
        
        with open(STREAKS_FILE, "w") as f:
            json.dump({"highest": highest_hash, "current": current_serializable}, f, indent=2)
    except Exception as e:
        print(f"ERROR saving streaks: {e}")

highest_score_hash, current_score_hash = load_streaks()

def safe_eval(expr):
    """
    Safely evaluate a mathematical expression using AST.
    Only allows numeric literals and basic math operators: +, -, *, /, **
    """
    ALLOWED_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    
    def eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            else:
                raise TypeError(f"Only numeric constants are allowed, not {type(node.value).__name__}")
        
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in ALLOWED_OPS:
                raise ValueError(f"Operator {type(node.op).__name__} is not allowed")
            left = eval_node(node.left)
            right = eval_node(node.right)
            return ALLOWED_OPS[type(node.op)](left, right)
        
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in ALLOWED_OPS:
                raise ValueError(f"Operator {type(node.op).__name__} is not allowed")
            operand = eval_node(node.operand)
            return ALLOWED_OPS[type(node.op)](operand)
        
        elif isinstance(node, ast.Expression):
            return eval_node(node.body)
        
        else:
            raise ValueError(f"Expression type {type(node).__name__} is not allowed")
    
    try:
        parsed = ast.parse(expr, mode='eval')
        return eval_node(parsed)
    except SyntaxError:
        raise SyntaxError("Invalid mathematical expression")

intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='k?', intents=intents)

RED = discord.Color.from_str("#C8549A")
WHITE = discord.Color.from_str("#FFFFFF")

sticky_messages = {}

bot.remove_command('help')

@bot.event
async def on_ready():
    activity = discord.Activity(type=discord.ActivityType.watching, name="◟．　jump!　❀ ֹ ⊹")
    await bot.change_presence(status=discord.Status.idle, activity=activity)
    print(f'{bot.user} has connected to Discord!')
    print(f'Monitoring for vanity: {VANITY_STRING}')
    print(f'Guild ID: {GUILD_ID}')
    print(f'Role ID: {ROLE_ID}')
    print(f'Channel ID: {VANITY_CHANNEL_ID}')

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="<a:a37:1437978393227432086> help‎‎ ‎‎ menu",
        description="**k?help** - shows all commands of the bot\n**k?calc <expression>** - evaluate a math expression\n**k?say <message>** - make the bot say a message\n**k?sticky <message>** - enable sticky message\n**k?removesticky** - disable sticky message\n**k?currentstreak** - see your current streak\n**k?lbstreak** - see streak leaderboard\n**k?personalbest** - see your highest streak",
        color=RED,
        timestamp=ctx.message.created_at
    )
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f"♫⁺ /kaede's‎‎ ‎‎ personal‎‎ ‎‎ bot")
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def sticky(ctx, *, message: str):
    sticky_messages[ctx.channel.id] = {"text": message, "last_message": None}
    await ctx.send(f"sticky message set for this channel:\n> {message}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def removesticky(ctx):
    if ctx.channel.id in sticky_messages:
        last_msg = sticky_messages[ctx.channel.id].get("last_message")
        if last_msg:
            try:
                await last_msg.delete()
            except:
                pass
        del sticky_messages[ctx.channel.id]
        await ctx.send("sticky message removed from this channel!")
    else:
        await ctx.send("no sticky message is set for this channel")

@bot.command()
async def calc(ctx, *, expression: str):
    try:
        sanitized = expression.replace('^', '**').strip()
        result = safe_eval(sanitized)
        await ctx.send(f"**`{result}`**")
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as e:
        await ctx.send(f"Error: `{str(e)}`")
    except Exception as e:
        await ctx.send(f"Error: Invalid expression")

@bot.command()
async def say(ctx, *, message: str):
    await ctx.message.delete()
    await ctx.send(message)

@bot.command()
async def currentstreak(ctx):
    user_id = str(ctx.author.id)
    if user_id in current_score_hash:
        await ctx.send(f"> <@{ctx.author.id}>'s current streak is **{current_score_hash[user_id][0]}** days <:tiktok_happy:1371440799643861055>")
    else:
        await ctx.send("> <:00_warning:1373921609601126441> **you don't have a streak yet.**")

@bot.command()
async def personalbest(ctx):
    user_id = str(ctx.author.id)
    if user_id in highest_score_hash:
        await ctx.send(f"> <@{ctx.author.id}>'s highest streak is **{highest_score_hash[user_id][0]}** days <:tiktok_complacent:1371440774956322917>")
    else:
        await ctx.send("> <:00_warning:1373921609601126441> **you don't have a best streak yet.**")

@bot.command()
async def lbstreak(ctx):
    if not highest_score_hash:
        await ctx.send("> <:00_warning:1373921609601126441> **no leaderboard data available yet.**")
        return

    sorted_scores = sorted(highest_score_hash.values(), key=lambda x: x[0], reverse=True)
    leaderboard_msg = ""
    for i, (score, user) in enumerate(sorted_scores, start=1):
        leaderboard_msg += f"{i}. {user}: **{score}** days ♡\n"

    await ctx.send(leaderboard_msg)

@bot.event
async def on_presence_update(before, after):
    if after.guild.id != GUILD_ID:
        return

    guild = after.guild
    role = guild.get_role(ROLE_ID)
    channel = guild.get_channel(VANITY_CHANNEL_ID)

    if not role or not channel:
        return

    before_status = get_custom_status(before)
    after_status = get_custom_status(after)

    has_vanity_before = before_status and VANITY_STRING.lower() in before_status.lower()
    has_vanity_after = after_status and VANITY_STRING.lower() in after_status.lower()

    is_offline = after.status == discord.Status.offline

    if has_vanity_after and not has_vanity_before and not is_offline:
        if role not in after.roles:
            try:
                await after.add_roles(role, reason=f'Added {VANITY_STRING} to status')

                embed = discord.Embed(
                    description=(
                        '_ _\n_ _ <a:a0tomodachi9:1436677397343637586> 𓏼 thx for the **s**upp__ort__.\n'
                        '_ _ ♡˖ <a:a016:1436692509605494925> for **perks**, visit [here](https://discord.com/channels/1319396490543890482/1370412018720309248)! _ _\n'
                        '<:000001:1373901557250129961>'
                    ),
                    color=RED
                )
                embed.set_footer(
                    text=f"‎‎ ‎‎ ‎‎ ‎‎ ‎‎ ‎‎ ､‎‎ ‎‎ ‎‎ ‎‎ ❀‎‎ ‎‎ ‎‎ ‎‎ {after.name} added /kaede to their status",
                    icon_url=after.display_avatar.url
                )
                embed.set_thumbnail(url=after.display_avatar.url)

                await channel.send(embed=embed)
                print(f'Added role to {after.name} for having {VANITY_STRING} in status')
            except discord.Forbidden:
                print(f'Missing permissions to add role to {after.name}')
            except Exception as e:
                print(f'Error adding role to {after.name}: {e}')

    elif (not has_vanity_after or is_offline) and has_vanity_before:
        if role in after.roles:
            try:
                await after.remove_roles(role, reason=f'Removed {VANITY_STRING} from status or went offline')
                print(f'Removed role from {after.name} (status change or offline)')
            except discord.Forbidden:
                print(f'Missing permissions to remove role from {after.name}')
            except Exception as e:
                print(f'Error removing role from {after.name}: {e}')

    elif is_offline and role in after.roles:
        try:
            await after.remove_roles(role, reason='User went offline')
            print(f'Removed role from {after.name} (went offline)')
        except discord.Forbidden:
            print(f'Missing permissions to remove role from {after.name}')
        except Exception as e:
            print(f'Error removing role from {after.name}: {e}')

def get_custom_status(member):
    for activity in member.activities:
        if isinstance(activity, discord.CustomActivity):
            return activity.state
    return None

@bot.event
async def on_member_update(before, after):
    if before.premium_since is None and after.premium_since is not None:
        channel = discord.utils.get(after.guild.text_channels, name="﹒mail")
        if channel:
            embed = discord.Embed(
                description=f"_ _\n_ _ <a:a021:1436679656052097055> ♩ ⁺ tysm‎‎ ‎‎ for‎‎ ‎‎ the‎‎ ‎‎ **b**oos__t__.\n_ _ ୧˖ <:1_KaitoYay:1436539061342048316> for‎‎ ‎‎ **perks**,‎‎ ‎‎ visit‎‎ ‎‎ [here]( https://discord.com/channels/1319396490543890482/1370412018720309248 )!\n<:000001:1373901557250129961>",
                color=0x7159b5
            )
            embed.set_thumbnail(url=after.avatar.url if after.avatar else after.default_avatar.url)
            await channel.send(embed=embed)

@bot.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji) != TARGET_EMOJI:
        return

    if payload.channel_id == LAUGHBOARD_CHANNEL_ID:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    reaction = discord.utils.get(message.reactions, emoji=TARGET_EMOJI)
    if not reaction:
        return

    count = reaction.count

    laughboard_channel = guild.get_channel(LAUGHBOARD_CHANNEL_ID)
    if not laughboard_channel:
        return

    async for msg in laughboard_channel.history(limit=100):
        if msg.embeds and msg.embeds[0].timestamp == message.created_at:
            embed = msg.embeds[0]
            embed.set_footer(text=f"{count} {TARGET_EMOJI} reactions")
            await msg.edit(content=f"{count} {TARGET_EMOJI} reactions", embed=embed)
            return

    if count == THRESHOLD:
        embed = discord.Embed(
            description=message.content,
            color=WHITE,
            timestamp=message.created_at
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="jump to message", value=f"[click here ! !]({message.jump_url})", inline=False)
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        await laughboard_channel.send(content=f"{THRESHOLD} {TARGET_EMOJI} reactions", embed=embed)

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author.bot:
        return

    data = sticky_messages.get(message.channel.id)
    if data:
        try:
            if data.get("last_message"):
                try:
                    await data["last_message"].delete()
                except:
                    pass
            new_msg = await message.channel.send(data["text"])
            sticky_messages[message.channel.id]["last_message"] = new_msg
        except discord.Forbidden:
            print(f"Missing permission to send sticky message in {message.channel.name}")

    if message.channel.id == CHANNEL_ID:
        user = str(message.author)
        user_id = str(message.author.id)
        user_message = str(message.content)
        channel = str(message.channel.name)
        message_day = date.today()
        day_t = timedelta(1)
        yesterday_date = message_day - day_t
        print(f"{user_id}: {user_message} ({channel}) / {message_day}")

        if user_id not in highest_score_hash and user_id not in current_score_hash:
            highest_score_hash[user_id] = [1, user]
            current_score_hash[user_id] = [1, message_day]

        elif current_score_hash[user_id][1] == yesterday_date:
            current_score_hash[user_id][0] += 1
            current_score_hash[user_id][1] = message_day
            if highest_score_hash[user_id][0] <= current_score_hash[user_id][0]:
                highest_score_hash[user_id][0] = current_score_hash[user_id][0]
                highest_score_hash[user_id][1] = user

        elif (
            current_score_hash[user_id][1] != yesterday_date
            and current_score_hash[user_id][1] != date.today()
        ):
            if highest_score_hash[user_id][0] <= current_score_hash[user_id][0]:
                highest_score_hash[user_id][0] = current_score_hash[user_id][0]
                highest_score_hash[user_id][1] = user
            current_score_hash[user_id][0] = 1
            current_score_hash[user_id][1] = message_day

        save_streaks(highest_score_hash, current_score_hash)
        print(f"highest {highest_score_hash}, current {current_score_hash}")

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"ERROR: Failed to start bot: {e}")
