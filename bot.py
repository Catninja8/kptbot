import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import datetime
import random
import asyncio
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

# ---------- Data Storage ----------
os.makedirs('data', exist_ok=True)

def load_json(path):
    full = f'data/{path}'
    if not os.path.exists(full):
        return {}
    with open(full, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(f'data/{path}', 'w') as f:
        json.dump(data, f, indent=2)

def add_log(action, details, guild_id=None):
    logs = load_json('logs.json')
    if 'logs' not in logs:
        logs['logs'] = []
    logs['logs'].insert(0, {
        'action': action,
        'details': details,
        'guild_id': str(guild_id) if guild_id else None,
        'timestamp': datetime.datetime.utcnow().isoformat()
    })
    logs['logs'] = logs['logs'][:200]
    save_json('logs.json', logs)

# ---------- Bot Setup ----------
intents = discord.Intents.all()

def get_prefix(bot, message):
    settings = load_json('settings.json')
    return settings.get('prefix', '!')

class KPTBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, intents=intents)

    async def setup_hook(self):
        self.add_view(TicketPanelView())
        await self.tree.sync()
        print('✅ Slash commands synced!')

    async def on_ready(self):
        print(f'✅ Logged in as {self.user}')
        add_log('BOT_START', f'{self.user} came online')
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name="your server | /help"
        ))

bot = KPTBot()
bot.remove_command('help')

# ---------- Groq AI ----------
def ask_groq(user_message: str) -> str:
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return "⚠️ AI isn't set up yet — please contact a staff member for help!"

    system_prompt = (
        "You are KPT_BOT, the friendly AI assistant for the KaramPlaysThis Discord community. "
        "Your personality: professional, warm, energetic, and helpful — like a community manager who loves gaming.\n\n"
        "RULES:\n"
        "1. Answer ANY question helpfully. You are a general-purpose assistant.\n"
        "2. If the question is about KaramPlaysThis, the server, gaming, roles, tickets, rules, streams or giveaways — "
        "give an extra detailed, enthusiastic answer and tie it back to the community where possible.\n"
        "3. For general questions (coding, math, life, etc.) — answer fully but end with a fun line like "
        "'By the way, if you ever need server help, I'm always here! 🎮'\n"
        "4. If the message contains hate speech, slurs, threats, sexual content, or requests for harmful/illegal info — "
        "reply ONLY with: '⚠️ I can't help with that. Please keep things respectful! If you need server support, open a ticket. 🎫'\n"
        "5. Keep responses under 280 words. Use Discord markdown (**bold**, bullet points) to keep things clean.\n"
        "6. Always end positively and energetically! 🚀"
    )

    import json as _json
    payload = _json.dumps({
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }).encode('utf-8')

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"Groq error: {e}")
        return "⚠️ I'm having a moment — try again shortly! Need urgent help? Open a ticket in the server. 🎫"

# ---------- Helper: shared response embed ----------
def mod_embed(title, color, **fields):
    embed = discord.Embed(title=title, color=color, timestamp=datetime.datetime.utcnow())
    for k, v in fields.items():
        embed.add_field(name=k, value=v)
    return embed

# ---------- Events ----------
@bot.event
async def on_member_join(member):
    settings = load_json('settings.json')
    guild = member.guild
    if settings.get('welcome_enabled'):
        ch_id = settings.get('welcome_channel')
        channel = guild.get_channel(int(ch_id)) if ch_id else None
        if channel:
            msg = settings.get('welcome_message', 'Welcome {user} to {server}!')
            msg = msg.replace('{user}', member.mention).replace('{server}', guild.name).replace('{username}', member.name)
            embed = discord.Embed(description=msg, color=0x5865F2)
            embed.set_author(name=f'Welcome to {guild.name}!', icon_url=member.display_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
    if settings.get('autorole_enabled'):
        role_id = settings.get('autorole_id')
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                await member.add_roles(role)
                add_log('AUTOROLE', f'Gave {role.name} to {member}', guild.id)
    add_log('MEMBER_JOIN', f'{member} joined {guild.name}', guild.id)

@bot.event
async def on_member_remove(member):
    settings = load_json('settings.json')
    guild = member.guild
    if settings.get('leave_enabled'):
        ch_id = settings.get('leave_channel')
        channel = guild.get_channel(int(ch_id)) if ch_id else None
        if channel:
            msg = settings.get('leave_message', '{username} has left {server}.')
            msg = msg.replace('{user}', member.mention).replace('{server}', guild.name).replace('{username}', member.name)
            embed = discord.Embed(description=msg, color=0xFF4466)
            await channel.send(embed=embed)
    add_log('MEMBER_LEAVE', f'{member} left {guild.name}', guild.id)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # ---- DM Handler with Groq AI ----
    if isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            reply = ask_groq(message.content)
        short = message.content[:60] + '...' if len(message.content) > 60 else message.content
        add_log('DM_AI', f'{message.author}: {short}')
        if len(reply) > 2000:
            for i in range(0, len(reply), 2000):
                await message.channel.send(reply[i:i+2000])
        else:
            await message.channel.send(reply)
        return

    settings = load_json('settings.json')
    custom_cmds = load_json('custom_commands.json')
    prefix = settings.get('prefix', '!')
    if message.content.startswith(prefix):
        cmd_name = message.content[len(prefix):].split()[0].lower()
        if cmd_name in custom_cmds:
            await message.channel.send(custom_cmds[cmd_name])
            return
    if settings.get('automod_enabled'):
        content = message.content.lower()
        deleted = False
        if settings.get('automod_badwords'):
            if any(w in content for w in settings.get('bad_words', [])):
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} watch your language!', delete_after=5)
                add_log('AUTOMOD_WORD', f'Deleted message from {message.author}', message.guild.id)
                deleted = True
        if not deleted and settings.get('automod_caps'):
            if len(message.content) > 8 and sum(1 for c in message.content if c.isupper()) / len(message.content) > 0.7:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} no excessive caps!', delete_after=5)
                add_log('AUTOMOD_CAPS', f'Deleted caps from {message.author}', message.guild.id)
                deleted = True
        if not deleted and settings.get('automod_links'):
            if 'http://' in content or 'https://' in content or 'discord.gg/' in content:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} links are not allowed!', delete_after=5)
                add_log('AUTOMOD_LINK', f'Deleted link from {message.author}', message.guild.id)
                deleted = True
        if deleted:
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
    elif isinstance(error, commands.CommandNotFound):
        pass

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or 'custom_id' not in interaction.data:
        return
    custom_id = interaction.data['custom_id']
    if custom_id.startswith('close_'):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message('❌ Only staff can close tickets.', ephemeral=True)
            return
        embed = discord.Embed(description='🔒 Ticket closing in 5 seconds...', color=0xFF4466)
        await interaction.response.send_message(embed=embed)
        tickets = load_json('tickets.json')
        for t in tickets.get('tickets', []):
            if t.get('channel_id') == str(interaction.channel.id):
                t['status'] = 'closed'
        save_json('tickets.json', tickets)
        add_log('TICKET_CLOSE', f'{interaction.user} closed {interaction.channel.name}', interaction.guild.id)
        await asyncio.sleep(5)
        await interaction.channel.delete()
    elif custom_id.startswith('claim_'):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message('❌ Only staff can claim tickets.', ephemeral=True)
            return
        embed = discord.Embed(description=f'✋ Claimed by {interaction.user.mention}', color=0x00FF88)
        await interaction.response.send_message(embed=embed)
        add_log('TICKET_CLAIM', f'{interaction.user} claimed {interaction.channel.name}', interaction.guild.id)

# ============================================================
# PREFIX COMMANDS
# ============================================================

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

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=g.name, color=0x00d4ff)
    embed.add_field(name='Members', value=g.member_count)
    embed.add_field(name='Channels', value=len(g.channels))
    embed.add_field(name='Roles', value=len(g.roles))
    embed.add_field(name='Created', value=g.created_at.strftime('%b %d, %Y'))
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    prefix = get_prefix(bot, ctx.message)
    embed = discord.Embed(title='📖 KPT_BOT Commands', description=f'Prefix: `{prefix}` — Also supports `/` slash commands!', color=0x5865F2)
    embed.add_field(name='🛡️ Moderation', value=f'`{prefix}kick` `{prefix}ban` `{prefix}mute` `{prefix}unmute` `{prefix}warn` `{prefix}warnings` `{prefix}clearwarns` `{prefix}purge`', inline=False)
    embed.add_field(name='🎫 Tickets', value=f'`{prefix}ticket` `{prefix}closeticket`', inline=False)
    embed.add_field(name='🎉 Giveaways', value=f'`{prefix}giveaway` `{prefix}reroll`', inline=False)
    embed.add_field(name='📢 Other', value=f'`{prefix}announce` `{prefix}giverole` `{prefix}removerole` `{prefix}addcmd` `{prefix}delcmd` `{prefix}listcmds` `{prefix}serverinfo` `{prefix}ping` `{prefix}info`', inline=False)
    embed.set_footer(text='Tip: Type / to use slash commands with autocomplete!')
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason='No reason provided'):
    await member.kick(reason=reason)
    await ctx.send(embed=mod_embed('👢 Member Kicked', 0xFF4466, User=str(member), Reason=reason, Moderator=str(ctx.author)))
    add_log('KICK', f'{ctx.author} kicked {member} | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason='No reason provided'):
    await member.ban(reason=reason)
    await ctx.send(embed=mod_embed('🔨 Member Banned', 0xFF0000, User=str(member), Reason=reason, Moderator=str(ctx.author)))
    add_log('BAN', f'{ctx.author} banned {member} | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_name):
    banned = [entry async for entry in ctx.guild.bans()]
    for entry in banned:
        if str(entry.user) == user_name:
            await ctx.guild.unban(entry.user)
            await ctx.send(f'✅ Unbanned **{entry.user}**')
            add_log('UNBAN', f'{ctx.author} unbanned {entry.user}', ctx.guild.id)
            return
    await ctx.send('❌ User not found in ban list.')

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason='No reason provided'):
    await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
    await ctx.send(embed=mod_embed('🔇 Member Muted', 0xFFCC00, User=str(member), Duration=f'{minutes} minutes', Reason=reason))
    add_log('MUTE', f'{ctx.author} muted {member} for {minutes}m | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f'🔊 **{member}** unmuted.')
    add_log('UNMUTE', f'{ctx.author} unmuted {member}', ctx.guild.id)

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason='No reason provided'):
    warns = load_json('warns.json')
    uid = str(member.id)
    if uid not in warns:
        warns[uid] = []
    warns[uid].append({'reason': reason, 'by': str(ctx.author), 'time': datetime.datetime.utcnow().isoformat()})
    save_json('warns.json', warns)
    await ctx.send(embed=mod_embed('⚠️ Member Warned', 0xFF9900, User=str(member), Reason=reason, **{'Total Warns': len(warns[uid])}))
    add_log('WARN', f'{ctx.author} warned {member} | {reason}', ctx.guild.id)

@bot.command()
async def warnings(ctx, member: discord.Member):
    warns = load_json('warns.json')
    user_warns = warns.get(str(member.id), [])
    if not user_warns:
        return await ctx.send(f'✅ **{member}** has no warnings.')
    embed = discord.Embed(title=f'⚠️ Warnings for {member}', color=0xFF9900)
    for i, w in enumerate(user_warns, 1):
        embed.add_field(name=f'Warn #{i}', value=f"Reason: {w['reason']}\nBy: {w['by']}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def clearwarns(ctx, member: discord.Member):
    warns = load_json('warns.json')
    warns[str(member.id)] = []
    save_json('warns.json', warns)
    await ctx.send(f'✅ Cleared all warnings for **{member}**.')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f'🧹 Deleted {amount} messages.', delete_after=3)
    add_log('PURGE', f'{ctx.author} purged {amount} messages in #{ctx.channel.name}', ctx.guild.id)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def giverole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        return await ctx.send(f'❌ Role `{role_name}` not found.')
    await member.add_roles(role)
    await ctx.send(f'✅ Gave **{role.name}** to **{member}**.')
    add_log('ROLE_GIVE', f'{ctx.author} gave {role.name} to {member}', ctx.guild.id)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        return await ctx.send(f'❌ Role `{role_name}` not found.')
    await member.remove_roles(role)
    await ctx.send(f'✅ Removed **{role.name}** from **{member}**.')
    add_log('ROLE_REMOVE', f'{ctx.author} removed {role.name} from {member}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def announce(ctx, channel: discord.TextChannel, *, message: str):
    embed = discord.Embed(description=message, color=0x00d4ff, timestamp=datetime.datetime.utcnow())
    embed.set_author(name='📢 Announcement', icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f'Announced by {ctx.author}')
    await channel.send(embed=embed)
    await ctx.send(f'✅ Sent to {channel.mention}')
    add_log('ANNOUNCE', f'{ctx.author} announced in #{channel.name}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, minutes: int, winners: int, *, prize: str):
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
    embed = discord.Embed(title='🎉 GIVEAWAY 🎉', description=f'**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>\n\nReact with 🎉 to enter!', color=0x00FF88, timestamp=end_time)
    embed.set_footer(text=f'Hosted by {ctx.author}')
    msg = await ctx.send(embed=embed)
    await msg.add_reaction('🎉')
    add_log('GIVEAWAY_START', f'{ctx.author} started giveaway: {prize} ({winners} winners, {minutes}m)', ctx.guild.id)
    await asyncio.sleep(minutes * 60)
    msg = await ctx.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji='🎉')
    users = [u async for u in reaction.users() if not u.bot]
    if not users:
        await ctx.send('🎉 Giveaway ended but nobody entered!')
        return
    winner_list = random.sample(users, min(winners, len(users)))
    winner_mentions = ', '.join(w.mention for w in winner_list)
    await ctx.send(embed=discord.Embed(title='🎉 Giveaway Ended!', description=f'**Prize:** {prize}\n**Winner(s):** {winner_mentions}', color=0x00FF88))
    add_log('GIVEAWAY_END', f'Giveaway: {prize} | Winners: {[str(w) for w in winner_list]}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def reroll(ctx, message_id: int, winners: int = 1):
    try:
        msg = await ctx.channel.fetch_message(message_id)
        reaction = discord.utils.get(msg.reactions, emoji='🎉')
        users = [u async for u in reaction.users() if not u.bot]
        winner_list = random.sample(users, min(winners, len(users)))
        await ctx.send(f'🎉 New winner(s): {", ".join(w.mention for w in winner_list)}!')
    except:
        await ctx.send('❌ Could not find that message.')

@bot.command()
async def ticket(ctx, *, reason='General Support'):
    await _open_ticket(ctx.guild, ctx.author, ctx.channel, reason)

@bot.command()
async def closeticket(ctx):
    if 'ticket-' not in ctx.channel.name:
        return await ctx.send('❌ This is not a ticket channel.')
    await ctx.send('🔒 Closing in 5 seconds...')
    tickets = load_json('tickets.json')
    for t in tickets.get('tickets', []):
        if t.get('channel_id') == str(ctx.channel.id):
            t['status'] = 'closed'
    save_json('tickets.json', tickets)
    add_log('TICKET_CLOSE', f'{ctx.author} closed {ctx.channel.name}', ctx.guild.id)
    await asyncio.sleep(5)
    await ctx.channel.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def addcmd(ctx, name: str, *, response: str):
    cmds = load_json('custom_commands.json')
    cmds[name.lower()] = response
    save_json('custom_commands.json', cmds)
    await ctx.send(f'✅ Custom command `{get_prefix(bot, ctx.message)}{name}` created!')
    add_log('CUSTOM_CMD_ADD', f'{ctx.author} added command: {name}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def delcmd(ctx, name: str):
    cmds = load_json('custom_commands.json')
    if name.lower() in cmds:
        del cmds[name.lower()]
        save_json('custom_commands.json', cmds)
        await ctx.send(f'✅ Deleted `{name}`.')
    else:
        await ctx.send(f'❌ Command `{name}` not found.')

@bot.command()
async def listcmds(ctx):
    cmds = load_json('custom_commands.json')
    prefix = get_prefix(bot, ctx.message)
    if not cmds:
        return await ctx.send('No custom commands yet.')
    embed = discord.Embed(title='Custom Commands', color=0x5865F2)
    for name, resp in cmds.items():
        embed.add_field(name=f'`{prefix}{name}`', value=resp[:50], inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, prefix: str):
    settings = load_json('settings.json')
    settings['prefix'] = prefix
    save_json('settings.json', settings)
    await ctx.send(f'✅ Prefix changed to `{prefix}`')
    add_log('SETTINGS', f'{ctx.author} changed prefix to {prefix}', ctx.guild.id)

# ============================================================
# SLASH COMMANDS
# ============================================================

@bot.tree.command(name='ping', description='Check the bot\'s latency')
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'🏓 Pong! `{round(bot.latency * 1000)}ms`')

@bot.tree.command(name='info', description='Show bot information')
async def slash_info(interaction: discord.Interaction):
    embed = discord.Embed(title='KPT_BOT Info', color=0x5865F2)
    embed.add_field(name='Servers', value=len(bot.guilds))
    embed.add_field(name='Users', value=sum(g.member_count for g in bot.guilds))
    embed.add_field(name='Ping', value=f'{round(bot.latency * 1000)}ms')
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='serverinfo', description='Show server information')
async def slash_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=g.name, color=0x00d4ff)
    embed.add_field(name='Members', value=g.member_count)
    embed.add_field(name='Channels', value=len(g.channels))
    embed.add_field(name='Roles', value=len(g.roles))
    embed.add_field(name='Created', value=g.created_at.strftime('%b %d, %Y'))
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='help', description='Show all KPT_BOT commands')
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title='📖 KPT_BOT Commands', description='Use `/` for slash commands or `!` for prefix commands', color=0x5865F2)
    embed.add_field(name='🛡️ Moderation', value='`/kick` `/ban` `/mute` `/unmute` `/warn` `/warnings` `/purge`', inline=False)
    embed.add_field(name='🎫 Tickets', value='`/ticket` `/closeticket`', inline=False)
    embed.add_field(name='🎉 Giveaways', value='`/giveaway` `/reroll`', inline=False)
    embed.add_field(name='📢 Other', value='`/announce` `/giverole` `/removerole` `/serverinfo` `/ping` `/info`', inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='kick', description='Kick a member from the server')
@app_commands.describe(member='The member to kick', reason='Reason for the kick')
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = 'No reason provided'):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    await member.kick(reason=reason)
    await interaction.followup.send(embed=mod_embed('👢 Member Kicked', 0xFF4466, User=str(member), Reason=reason, Moderator=str(interaction.user)))
    add_log('KICK', f'{interaction.user} kicked {member} | {reason}', interaction.guild.id)

@bot.tree.command(name='ban', description='Ban a member from the server')
@app_commands.describe(member='The member to ban', reason='Reason for the ban')
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = 'No reason provided'):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    await member.ban(reason=reason)
    await interaction.followup.send(embed=mod_embed('🔨 Member Banned', 0xFF0000, User=str(member), Reason=reason, Moderator=str(interaction.user)))
    add_log('BAN', f'{interaction.user} banned {member} | {reason}', interaction.guild.id)

@bot.tree.command(name='mute', description='Timeout (mute) a member')
@app_commands.describe(member='The member to mute', minutes='Duration in minutes', reason='Reason')
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = 'No reason provided'):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
    await interaction.followup.send(embed=mod_embed('🔇 Member Muted', 0xFFCC00, User=str(member), Duration=f'{minutes} minutes', Reason=reason))
    add_log('MUTE', f'{interaction.user} muted {member} for {minutes}m | {reason}', interaction.guild.id)

@bot.tree.command(name='unmute', description='Remove a timeout from a member')
@app_commands.describe(member='The member to unmute')
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    await member.timeout(None)
    await interaction.followup.send(f'🔊 **{member}** has been unmuted.')
    add_log('UNMUTE', f'{interaction.user} unmuted {member}', interaction.guild.id)

@bot.tree.command(name='warn', description='Warn a member')
@app_commands.describe(member='The member to warn', reason='Reason for the warning')
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str = 'No reason provided'):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    warns = load_json('warns.json')
    uid = str(member.id)
    if uid not in warns:
        warns[uid] = []
    warns[uid].append({'reason': reason, 'by': str(interaction.user), 'time': datetime.datetime.utcnow().isoformat()})
    save_json('warns.json', warns)
    await interaction.followup.send(embed=mod_embed('⚠️ Member Warned', 0xFF9900, User=str(member), Reason=reason, **{'Total Warns': len(warns[uid])}))
    add_log('WARN', f'{interaction.user} warned {member} | {reason}', interaction.guild.id)

@bot.tree.command(name='warnings', description='View warnings for a member')
@app_commands.describe(member='The member to check')
async def slash_warnings(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    warns = load_json('warns.json')
    user_warns = warns.get(str(member.id), [])
    if not user_warns:
        return await interaction.followup.send(f'✅ **{member}** has no warnings.')
    embed = discord.Embed(title=f'⚠️ Warnings for {member}', color=0xFF9900)
    for i, w in enumerate(user_warns, 1):
        embed.add_field(name=f'Warn #{i}', value=f"Reason: {w['reason']}\nBy: {w['by']}", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='purge', description='Delete a number of messages')
@app_commands.describe(amount='Number of messages to delete')
async def slash_purge(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.send_message(f'🧹 Deleting {amount} messages...', ephemeral=True)
    await interaction.channel.purge(limit=amount)
    add_log('PURGE', f'{interaction.user} purged {amount} messages in #{interaction.channel.name}', interaction.guild.id)

@bot.tree.command(name='ticket', description='Open a support ticket')
@app_commands.describe(reason='What do you need help with?')
async def slash_ticket(interaction: discord.Interaction, reason: str = 'General Support'):
    await interaction.response.defer(ephemeral=True)
    channel = await _open_ticket(interaction.guild, interaction.user, None, reason)
    await interaction.followup.send(f'✅ Ticket created: {channel.mention}', ephemeral=True)

@bot.tree.command(name='closeticket', description='Close the current ticket channel')
async def slash_closeticket(interaction: discord.Interaction):
    if 'ticket-' not in interaction.channel.name:
        return await interaction.response.send_message('❌ This is not a ticket channel.', ephemeral=True)
    await interaction.response.send_message('🔒 Closing in 5 seconds...')
    tickets = load_json('tickets.json')
    for t in tickets.get('tickets', []):
        if t.get('channel_id') == str(interaction.channel.id):
            t['status'] = 'closed'
    save_json('tickets.json', tickets)
    add_log('TICKET_CLOSE', f'{interaction.user} closed {interaction.channel.name}', interaction.guild.id)
    await asyncio.sleep(5)
    await interaction.channel.delete()

@bot.tree.command(name='giverole', description='Give a role to a member')
@app_commands.describe(member='The member', role='The role to give')
async def slash_giverole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    await member.add_roles(role)
    await interaction.followup.send(f'✅ Gave **{role.name}** to **{member}**.')
    add_log('ROLE_GIVE', f'{interaction.user} gave {role.name} to {member}', interaction.guild.id)

@bot.tree.command(name='removerole', description='Remove a role from a member')
@app_commands.describe(member='The member', role='The role to remove')
async def slash_removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    await member.remove_roles(role)
    await interaction.followup.send(f'✅ Removed **{role.name}** from **{member}**.')
    add_log('ROLE_REMOVE', f'{interaction.user} removed {role.name} from {member}', interaction.guild.id)

@bot.tree.command(name='announce', description='Send an announcement to a channel')
@app_commands.describe(channel='Channel to announce in', message='The announcement message')
async def slash_announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(description=message, color=0x00d4ff, timestamp=datetime.datetime.utcnow())
    embed.set_author(name='📢 Announcement', icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f'Announced by {interaction.user}')
    await channel.send(embed=embed)
    await interaction.followup.send(f'✅ Announcement sent to {channel.mention}!', ephemeral=True)
    add_log('ANNOUNCE', f'{interaction.user} announced in #{channel.name}', interaction.guild.id)

@bot.tree.command(name='giveaway', description='Start a giveaway')
@app_commands.describe(minutes='Duration in minutes', winners='Number of winners', prize='What are you giving away?')
async def slash_giveaway(interaction: discord.Interaction, minutes: int, winners: int, prize: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message('❌ No permission.', ephemeral=True)
    await interaction.response.defer()
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
    embed = discord.Embed(title='🎉 GIVEAWAY 🎉', description=f'**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>\n\nReact with 🎉 to enter!', color=0x00FF88, timestamp=end_time)
    embed.set_footer(text=f'Hosted by {interaction.user}')
    msg = await interaction.followup.send(embed=embed)
    await msg.add_reaction('🎉')
    add_log('GIVEAWAY_START', f'{interaction.user} started: {prize} ({winners}w {minutes}m)', interaction.guild.id)
    await asyncio.sleep(minutes * 60)
    msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji='🎉')
    users = [u async for u in reaction.users() if not u.bot]
    if not users:
        await interaction.channel.send('🎉 Giveaway ended but nobody entered!')
        return
    winner_list = random.sample(users, min(winners, len(users)))
    winner_mentions = ', '.join(w.mention for w in winner_list)
    await interaction.channel.send(embed=discord.Embed(title='🎉 Giveaway Ended!', description=f'**Prize:** {prize}\n**Winner(s):** {winner_mentions}', color=0x00FF88))
    add_log('GIVEAWAY_END', f'Giveaway: {prize} | Winners: {[str(w) for w in winner_list]}', interaction.guild.id)

# ============================================================
# TICKET PANEL SYSTEM — Modals + Dropdown
# ============================================================

TICKET_CATEGORIES = {
    'general':   {'label': '🙋 General Support',   'slug': 'general',     'color': 0x5865F2},
    'stream':    {'label': '🔴 Stream Problem',     'slug': 'stream',      'color': 0xFF4466},
    'report':    {'label': '🚨 Report a Player',    'slug': 'report',      'color': 0xFF9900},
    'partner':   {'label': '🤝 Partnership',        'slug': 'partnership', 'color': 0x00d4ff},
    'other':     {'label': '❓ Other',              'slug': 'other',       'color': 0x8892b0},
}

# ---------- Modals (popup forms) per category ----------

class GeneralModal(discord.ui.Modal, title='🙋 General Support'):
    issue = discord.ui.TextInput(label='What do you need help with?', style=discord.TextStyle.short, placeholder='Brief summary of your issue...', max_length=100)
    details = discord.ui.TextInput(label='Please describe in detail', style=discord.TextStyle.long, placeholder='Give us as much info as possible so we can help you faster...', max_length=1000)
    tried = discord.ui.TextInput(label='What have you already tried?', style=discord.TextStyle.short, placeholder='e.g. Checked FAQ, asked in chat...', required=False, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {
            'Issue': str(self.issue),
            'Details': str(self.details),
            'Already Tried': str(self.tried) or 'Nothing mentioned',
        }
        await _create_ticket_channel(interaction, 'General Support', 'general', fields)


class StreamModal(discord.ui.Modal, title='🔴 Stream Problem'):
    problem = discord.ui.TextInput(label='What is the stream problem?', style=discord.TextStyle.short, placeholder='e.g. Cannot watch stream, buffering, no audio...', max_length=100)
    platform = discord.ui.TextInput(label='Which platform? (Twitch / YouTube / Other)', style=discord.TextStyle.short, placeholder='e.g. Twitch', max_length=50)
    device = discord.ui.TextInput(label='What device are you using?', style=discord.TextStyle.short, placeholder='e.g. PC, Phone, Xbox...', max_length=50)
    details = discord.ui.TextInput(label='Any extra details?', style=discord.TextStyle.long, placeholder='Error messages, screenshots, when it started...', required=False, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {
            'Problem': str(self.problem),
            'Platform': str(self.platform),
            'Device': str(self.device),
            'Extra Details': str(self.details) or 'None provided',
        }
        await _create_ticket_channel(interaction, 'Stream Problem', 'stream', fields)


class ReportModal(discord.ui.Modal, title='🚨 Report a Player'):
    reported_user = discord.ui.TextInput(label='Username of the player you are reporting', style=discord.TextStyle.short, placeholder='e.g. BadUser#1234', max_length=100)
    reason = discord.ui.TextInput(label='Reason for report', style=discord.TextStyle.short, placeholder='e.g. Harassment, cheating, spam...', max_length=100)
    what_happened = discord.ui.TextInput(label='What happened? (full details)', style=discord.TextStyle.long, placeholder='Describe the full situation in detail...', max_length=1000)
    evidence = discord.ui.TextInput(label='Do you have evidence? (screenshots/links)', style=discord.TextStyle.short, placeholder='Yes / No — attach screenshots in the ticket channel', required=False, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {
            'Reported User': str(self.reported_user),
            'Reason': str(self.reason),
            'What Happened': str(self.what_happened),
            'Evidence': str(self.evidence) or 'None mentioned',
        }
        await _create_ticket_channel(interaction, 'Report a Player', 'report', fields)


class PartnerModal(discord.ui.Modal, title='🤝 Partnership Request'):
    name = discord.ui.TextInput(label='Your name / brand name', style=discord.TextStyle.short, placeholder='e.g. YourBrand', max_length=100)
    platform = discord.ui.TextInput(label='Your platform & follower count', style=discord.TextStyle.short, placeholder='e.g. YouTube — 5,000 subs', max_length=100)
    proposal = discord.ui.TextInput(label='What are you proposing?', style=discord.TextStyle.long, placeholder='Describe what kind of partnership you are looking for...', max_length=1000)
    links = discord.ui.TextInput(label='Your channel / social links', style=discord.TextStyle.short, placeholder='e.g. youtube.com/yourchannel', max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {
            'Brand Name': str(self.name),
            'Platform & Size': str(self.platform),
            'Proposal': str(self.proposal),
            'Links': str(self.links),
        }
        await _create_ticket_channel(interaction, 'Partnership', 'partner', fields)


class OtherModal(discord.ui.Modal, title='❓ Other'):
    subject = discord.ui.TextInput(label='Subject', style=discord.TextStyle.short, placeholder='Brief subject of your ticket...', max_length=100)
    details = discord.ui.TextInput(label='Full details', style=discord.TextStyle.long, placeholder='Explain your situation in full detail...', max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {
            'Subject': str(self.subject),
            'Details': str(self.details),
        }
        await _create_ticket_channel(interaction, 'Other', 'other', fields)


MODAL_MAP = {
    'general': GeneralModal,
    'stream':  StreamModal,
    'report':  ReportModal,
    'partner': PartnerModal,
    'other':   OtherModal,
}

# ---------- Dropdown select ----------

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='🙋 General Support',  value='general',  description='General questions or server help'),
            discord.SelectOption(label='🔴 Stream Problem',   value='stream',   description='Issues watching KaramPlaysThis streams'),
            discord.SelectOption(label='🚨 Report a Player',  value='report',   description='Report a member for rule breaking'),
            discord.SelectOption(label='🤝 Partnership',      value='partner',  description='Partnership or collab requests'),
            discord.SelectOption(label='❓ Other',            value='other',    description='Anything else not listed above'),
        ]
        super().__init__(placeholder='📂 Select a ticket category...', min_values=1, max_values=1, options=options, custom_id='ticket_dropdown')

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        modal_class = MODAL_MAP.get(category)
        if modal_class:
            await interaction.response.send_modal(modal_class())


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ---------- Core: create the ticket channel ----------

async def _create_ticket_channel(interaction: discord.Interaction, category_name: str, slug: str, fields: dict):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    user = interaction.user
    settings = load_json('settings.json')
    tickets = load_json('tickets.json')

    if 'count' not in tickets:
        tickets['count'] = 0
    tickets['count'] += 1
    ticket_num = tickets['count']

    channel_name = f'ticket-{ticket_num:04d}-{slug}'
    category_id = settings.get('ticket_category')
    category = guild.get_channel(int(category_id)) if category_id else None
    support_role_id = settings.get('ticket_support_role')
    support_role = guild.get_role(int(support_role_id)) if support_role_id else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await guild.create_text_channel(
        channel_name,
        overwrites=overwrites,
        category=category,
        topic=f'Ticket #{ticket_num:04d} | {category_name} | {user}'
    )

    # Save ticket
    if 'tickets' not in tickets:
        tickets['tickets'] = []
    tickets['tickets'].insert(0, {
        'id': ticket_num,
        'user': str(user),
        'user_id': str(user.id),
        'category': category_name,
        'channel': channel_name,
        'channel_id': str(channel.id),
        'status': 'open',
        'time': datetime.datetime.utcnow().isoformat()
    })
    save_json('tickets.json', tickets)

    # Build the ticket info embed with all form answers
    cat_info = TICKET_CATEGORIES.get(slug, {})
    color = cat_info.get('color', 0x5865F2)

    embed = discord.Embed(
        title=f'🎫 Ticket #{ticket_num:04d} — {category_name}',
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    embed.add_field(name='📋 Category', value=category_name, inline=True)
    embed.add_field(name='👤 Opened By', value=user.mention, inline=True)
    embed.add_field(name='\u200b', value='\u200b', inline=True)

    # Add all form answers as fields
    for label, value in fields.items():
        embed.add_field(name=f'❯ {label}', value=value[:1024], inline=False)

    embed.set_footer(text='KPT_BOT Ticket System • Support will be with you shortly!')

    # Ticket management buttons
    btn_view = discord.ui.View(timeout=None)
    btn_view.add_item(discord.ui.Button(label='🔒 Close Ticket', style=discord.ButtonStyle.danger, custom_id=f'close_{channel.id}'))
    btn_view.add_item(discord.ui.Button(label='✋ Claim', style=discord.ButtonStyle.secondary, custom_id=f'claim_{channel.id}'))

    mention_str = f'{user.mention}{" " + support_role.mention if support_role else ""}'
    await channel.send(mention_str, embed=embed, view=btn_view)

    await interaction.followup.send(f'✅ Your ticket has been created: {channel.mention}', ephemeral=True)
    add_log('TICKET_OPEN', f'{user} opened ticket #{ticket_num:04d}: {category_name}', guild.id)
    return channel


# ---------- Legacy ticket command (kept for ! prefix) ----------
async def _open_ticket(guild, user, reply_channel, reason):
    settings = load_json('settings.json')
    tickets = load_json('tickets.json')
    if 'count' not in tickets:
        tickets['count'] = 0
    tickets['count'] += 1
    ticket_num = tickets['count']
    topic_slug = reason.lower().replace(' ', '-')[:20]
    channel_name = f'ticket-{ticket_num:04d}-{topic_slug}'
    category_id = settings.get('ticket_category')
    category = guild.get_channel(int(category_id)) if category_id else None
    support_role_id = settings.get('ticket_support_role')
    support_role = guild.get_role(int(support_role_id)) if support_role_id else None
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category, topic=f'Ticket #{ticket_num:04d} | {user} | {reason}')
    if 'tickets' not in tickets:
        tickets['tickets'] = []
    tickets['tickets'].insert(0, {
        'id': ticket_num, 'user': str(user), 'user_id': str(user.id),
        'category': reason, 'channel': channel_name, 'channel_id': str(channel.id),
        'status': 'open', 'time': datetime.datetime.utcnow().isoformat()
    })
    save_json('tickets.json', tickets)
    embed = discord.Embed(title=f'🎫 Ticket #{ticket_num:04d}', description=f'**Topic:** {reason}\n**Opened by:** {user.mention}\n\nSupport will be with you shortly!', color=0x5865F2, timestamp=datetime.datetime.utcnow())
    embed.set_footer(text='KPT_BOT Ticket System')
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label='🔒 Close Ticket', style=discord.ButtonStyle.danger, custom_id=f'close_{channel.id}'))
    view.add_item(discord.ui.Button(label='✋ Claim', style=discord.ButtonStyle.secondary, custom_id=f'claim_{channel.id}'))
    mention_str = f'{user.mention}{" " + support_role.mention if support_role else ""}'
    await channel.send(mention_str, embed=embed, view=view)
    add_log('TICKET_OPEN', f'{user} opened ticket #{ticket_num:04d}: {reason}', guild.id)
    return channel


# ---------- /ticketpanel — post the panel in a channel ----------
@bot.tree.command(name='ticketpanel', description='Post the ticket panel in this channel')
async def slash_ticketpanel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title='🎫 KaramPlaysThis Support',
        description=(
            '**Need help? Open a ticket below!**\n\n'
            '🙋 **General Support** — General questions or server help\n'
            '🔴 **Stream Problem** — Issues with KaramPlaysThis streams\n'
            '🚨 **Report a Player** — Report someone breaking the rules\n'
            '🤝 **Partnership** — Collab or partnership requests\n'
            '❓ **Other** — Anything else\n\n'
            '> Select a category from the dropdown below to get started.\n'
            '> You will be asked a few quick questions before your ticket is created.'
        ),
        color=0x5865F2,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text='KPT_BOT Ticket System • One ticket per issue please!')
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    await interaction.channel.send(embed=embed, view=TicketPanelView())
    await interaction.followup.send('✅ Ticket panel posted!', ephemeral=True)
    add_log('TICKET_PANEL', f'{interaction.user} posted ticket panel in #{interaction.channel.name}', interaction.guild.id)


# ---------- Run ----------
bot.run(os.getenv('DISCORD_TOKEN'))
