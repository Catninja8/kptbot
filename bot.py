import discord
from discord.ext import commands
import os
import json
import datetime
from dotenv import load_dotenv

load_dotenv()

# ---------- Data Storage ----------
WARNS_FILE = 'data/warns.json'
SETTINGS_FILE = 'data/settings.json'
LOGS_FILE = 'data/logs.json'
TICKETS_FILE = 'data/tickets.json'

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def add_log(action, details):
    logs = load_json(LOGS_FILE)
    if 'logs' not in logs:
        logs['logs'] = []
    logs['logs'].insert(0, {
        'action': action,
        'details': details,
        'timestamp': datetime.datetime.utcnow().isoformat()
    })
    logs['logs'] = logs['logs'][:100]  # Keep last 100
    save_json(LOGS_FILE, logs)

# ---------- Intents & Bot ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

def get_prefix(bot, message):
    settings = load_json(SETTINGS_FILE)
    return settings.get('prefix', '!')

bot = commands.Bot(command_prefix=get_prefix, intents=intents)

# ---------- Events ----------
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    add_log('BOT_START', f'{bot.user} came online')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Auto-mod bad words filter
    settings = load_json(SETTINGS_FILE)
    if settings.get('automod', False):
        bad_words = settings.get('bad_words', [])
        content_lower = message.content.lower()
        if any(word in content_lower for word in bad_words):
            await message.delete()
            await message.channel.send(f'⚠️ {message.author.mention}, your message was removed for containing a banned word.')
            add_log('AUTOMOD', f'Deleted message from {message.author} in #{message.channel.name}')
            return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('❌ You don\'t have permission to use this command.')
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send('❌ Member not found.')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'❌ Missing argument: `{error.param.name}`')

# ---------- Basic ----------
@bot.command()
async def ping(ctx):
    await ctx.send(f'🏓 Pong! `{round(bot.latency * 1000)}ms`')

@bot.command()
async def info(ctx):
    embed = discord.Embed(title='KPT_BOT Info', color=0x5865F2)
    embed.add_field(name='Servers', value=len(bot.guilds))
    embed.add_field(name='Users', value=sum(g.member_count for g in bot.guilds))
    embed.add_field(name='Ping', value=f'{round(bot.latency * 1000)}ms')
    await ctx.send(embed=embed)

# ---------- Moderation ----------
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason='No reason provided'):
    await member.kick(reason=reason)
    await ctx.send(f'👢 **{member}** has been kicked. Reason: {reason}')
    add_log('KICK', f'{ctx.author} kicked {member} | Reason: {reason}')

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason='No reason provided'):
    await member.ban(reason=reason)
    await ctx.send(f'🔨 **{member}** has been banned. Reason: {reason}')
    add_log('BAN', f'{ctx.author} banned {member} | Reason: {reason}')

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason='No reason provided'):
    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f'🔇 **{member}** has been muted for {minutes} minutes. Reason: {reason}')
    add_log('MUTE', f'{ctx.author} muted {member} for {minutes}m | Reason: {reason}')

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f'🔊 **{member}** has been unmuted.')
    add_log('UNMUTE', f'{ctx.author} unmuted {member}')

@bot.command()
async def warn(ctx, member: discord.Member, *, reason='No reason provided'):
    if not ctx.author.guild_permissions.kick_members:
        return await ctx.send('❌ No permission.')
    warns = load_json(WARNS_FILE)
    uid = str(member.id)
    if uid not in warns:
        warns[uid] = []
    warns[uid].append({'reason': reason, 'by': str(ctx.author), 'time': datetime.datetime.utcnow().isoformat()})
    save_json(WARNS_FILE, warns)
    await ctx.send(f'⚠️ **{member}** has been warned. Reason: {reason} (Total warns: {len(warns[uid])})')
    add_log('WARN', f'{ctx.author} warned {member} | Reason: {reason}')

@bot.command()
async def warnings(ctx, member: discord.Member):
    warns = load_json(WARNS_FILE)
    uid = str(member.id)
    user_warns = warns.get(uid, [])
    if not user_warns:
        return await ctx.send(f'✅ **{member}** has no warnings.')
    embed = discord.Embed(title=f'Warnings for {member}', color=0xFF9900)
    for i, w in enumerate(user_warns, 1):
        embed.add_field(name=f'Warn #{i}', value=f"Reason: {w['reason']}\nBy: {w['by']}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def clearwarns(ctx, member: discord.Member):
    warns = load_json(WARNS_FILE)
    warns[str(member.id)] = []
    save_json(WARNS_FILE, warns)
    await ctx.send(f'✅ Cleared all warnings for **{member}**.')

@bot.command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, prefix: str):
    settings = load_json(SETTINGS_FILE)
    settings['prefix'] = prefix
    save_json(SETTINGS_FILE, settings)
    await ctx.send(f'✅ Prefix changed to `{prefix}`')
    add_log('SETTINGS', f'{ctx.author} changed prefix to {prefix}')

# ---------- Tickets ----------
@bot.command()
async def ticket(ctx, *, reason='Support needed'):
    guild = ctx.guild
    settings = load_json(SETTINGS_FILE)
    category_id = settings.get('ticket_category')
    category = discord.utils.get(guild.categories, id=category_id) if category_id else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    # Give admins access
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await guild.create_text_channel(
        f'ticket-{ctx.author.name}',
        overwrites=overwrites,
        category=category,
        topic=f'Ticket by {ctx.author} | Reason: {reason}'
    )

    tickets = load_json(TICKETS_FILE)
    if 'tickets' not in tickets:
        tickets['tickets'] = []
    tickets['tickets'].insert(0, {
        'user': str(ctx.author),
        'reason': reason,
        'channel': channel.name,
        'status': 'open',
        'time': datetime.datetime.utcnow().isoformat()
    })
    save_json(TICKETS_FILE, tickets)

    embed = discord.Embed(title='🎫 Ticket Created', description=f'Your ticket has been created in {channel.mention}', color=0x00FF88)
    await ctx.send(embed=embed)
    await channel.send(f'👋 {ctx.author.mention}, support will be with you shortly!\n**Reason:** {reason}\n\nType `!closeticket` to close this ticket.')
    add_log('TICKET_OPEN', f'{ctx.author} opened ticket: {reason}')

@bot.command()
async def closeticket(ctx):
    if 'ticket-' not in ctx.channel.name:
        return await ctx.send('❌ This is not a ticket channel.')
    await ctx.send('🔒 Closing ticket in 5 seconds...')
    await discord.utils.sleep_until(datetime.datetime.utcnow() + datetime.timedelta(seconds=5))
    await ctx.channel.delete()
    add_log('TICKET_CLOSE', f'Ticket {ctx.channel.name} closed by {ctx.author}')

# ---------- Admin ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def automod(ctx, state: str):
    settings = load_json(SETTINGS_FILE)
    settings['automod'] = state.lower() == 'on'
    save_json(SETTINGS_FILE, settings)
    await ctx.send(f'✅ Auto-mod is now **{"ON" if settings["automod"] else "OFF"}**')

@bot.command()
@commands.has_permissions(administrator=True)
async def addbadword(ctx, word: str):
    settings = load_json(SETTINGS_FILE)
    if 'bad_words' not in settings:
        settings['bad_words'] = []
    if word.lower() not in settings['bad_words']:
        settings['bad_words'].append(word.lower())
        save_json(SETTINGS_FILE, settings)
        await ctx.send(f'✅ Added `{word}` to bad words list.')
    else:
        await ctx.send('⚠️ That word is already in the list.')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f'🧹 Deleted {amount} messages.', delete_after=3)
    add_log('PURGE', f'{ctx.author} purged {amount} messages in #{ctx.channel.name}')

# ---------- Run ----------
bot.run(os.getenv('DISCORD_TOKEN'))
