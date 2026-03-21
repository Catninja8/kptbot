import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, random, asyncio, urllib.request, urllib.error
from dotenv import load_dotenv
load_dotenv()

os.makedirs('data', exist_ok=True)

# ---------- Data ----------
def load_json(path):
    full = f'data/{path}'
    if not os.path.exists(full): return {}
    with open(full, 'r') as f: return json.load(f)

def save_json(path, data):
    with open(f'data/{path}', 'w') as f: json.dump(data, f, indent=2)

def add_log(action, details, guild_id=None):
    logs = load_json('logs.json')
    if 'logs' not in logs: logs['logs'] = []
    logs['logs'].insert(0, {'action': action, 'details': details, 'guild_id': str(guild_id) if guild_id else None, 'timestamp': datetime.datetime.utcnow().isoformat()})
    logs['logs'] = logs['logs'][:200]
    save_json('logs.json', logs)

# ---------- Messages Config ----------
DEFAULT_MSGS = {
    "colors": {"kick":"FF4466","ban":"FF0000","mute":"FFCC00","unmute":"00FF88","warn":"FF9900","purge":"00d4ff","giveaway":"00FF88","announce":"00d4ff","ticket":"5865F2","welcome":"5865F2","leave":"FF4466"},
    "moderation": {"kick_title":"👢 Member Kicked","ban_title":"🔨 Member Banned","mute_title":"🔇 Member Muted","unmute_title":"🔊 Member Unmuted","unmute_msg":"🔊 **{user}** has been unmuted.","warn_title":"⚠️ Member Warned","purge_msg":"🧹 Deleted {amount} messages.","no_permission":"❌ You don't have permission to use this command.","member_not_found":"❌ Member not found.","missing_argument":"❌ Missing argument: `{arg}`","kick_dm":"You have been kicked from {server}. Reason: {reason}","ban_dm":"You have been banned from {server}. Reason: {reason}"},
    "tickets": {"open_confirm":"✅ Your ticket has been created: {channel}","close_countdown":"🔒 Ticket closing in 5 seconds...","claim_msg":"✋ Ticket claimed by {user}","ticket_footer":"KPT_BOT Ticket System • Support will be with you shortly!","not_ticket_channel":"❌ This is not a ticket channel.","close_perms":"❌ Only staff can close tickets.","claim_perms":"❌ Only staff can claim tickets."},
    "giveaway": {"title":"🎉 GIVEAWAY 🎉","enter_instruction":"React with 🎉 to enter!","end_title":"🎉 Giveaway Ended!","no_entries":"🎉 Giveaway ended but nobody entered!","winners_msg":"Congratulations {winners}! You won **{prize}**! 🎉","footer":"Hosted by {host}"},
    "automod": {"badword_msg":"⚠️ {user} watch your language!","caps_msg":"⚠️ {user} please don't use excessive caps!","link_msg":"⚠️ {user} links are not allowed here!"},
    "welcome": {"author_text":"Welcome to {server}!"},
    "roles": {"give_msg":"✅ Gave **{role}** to **{user}**.","remove_msg":"✅ Removed **{role}** from **{user}**.","role_not_found":"❌ Role `{role}` not found."},
    "general": {"ping_msg":"🏓 Pong! `{latency}ms`","bot_status":"watching your server | /help","status_type":"watching"}
}

def get_msgs():
    cfg = load_json('messages_config.json')
    if not cfg:
        save_json('messages_config.json', DEFAULT_MSGS)
        return DEFAULT_MSGS
    merged = json.loads(json.dumps(DEFAULT_MSGS))
    for section, vals in cfg.items():
        if section in merged and isinstance(vals, dict): merged[section].update(vals)
        else: merged[section] = vals
    return merged

def m(section, key, **kwargs):
    text = get_msgs().get(section, {}).get(key, f'[{section}.{key}]')
    for k, v in kwargs.items(): text = text.replace('{' + k + '}', str(v))
    return text

def color(key):
    try: return int(get_msgs()['colors'].get(key, '5865F2'), 16)
    except: return 0x5865F2

# ---------- Server Cache (for dashboard dropdowns) ----------
def update_server_cache(guild):
    """Write guild channels/roles to shared data folder in Discord order with categories."""
    # Build grouped channels in exact Discord order
    grouped = []

    # Uncategorised channels first (no category)
    uncategorised = [
        c for c in sorted(guild.channels, key=lambda x: x.position)
        if c.type in (discord.ChannelType.text, discord.ChannelType.news) and c.category is None
    ]
    if uncategorised:
        grouped.append({
            'category_id': None,
            'category_name': '📋 Uncategorised',
            'channels': [{'id': str(c.id), 'name': c.name} for c in uncategorised]
        })

    # Categorised channels in category order
    for cat in sorted(guild.categories, key=lambda x: x.position):
        channels = [
            c for c in sorted(cat.channels, key=lambda x: x.position)
            if c.type in (discord.ChannelType.text, discord.ChannelType.news)
        ]
        if channels:
            grouped.append({
                'category_id': str(cat.id),
                'category_name': f'📁 {cat.name.upper()}',
                'channels': [{'id': str(c.id), 'name': c.name} for c in channels]
            })

    # Flat channel list for backwards compat
    flat_channels = []
    for group in grouped:
        flat_channels.extend(group['channels'])

    # Roles sorted by position (highest first = most important)
    roles_sorted = sorted(
        [r for r in guild.roles if not r.is_default()],
        key=lambda x: x.position,
        reverse=True
    )

    cache = {
        'guild_id': str(guild.id),
        'guild_name': guild.name,
        'guild_icon': str(guild.icon.url) if guild.icon else None,
        'member_count': guild.member_count,
        'channels': flat_channels,
        'channels_grouped': grouped,
        'categories': [
            {'id': str(c.id), 'name': c.name}
            for c in sorted(guild.categories, key=lambda x: x.position)
        ],
        'roles': [
            {'id': str(r.id), 'name': r.name, 'color': str(r.color), 'position': r.position}
            for r in roles_sorted
        ],
        'updated': datetime.datetime.utcnow().isoformat()
    }
    save_json('server_cache.json', cache)

# ---------- Bot Setup ----------
intents = discord.Intents.all()

def get_prefix(bot, message):
    return load_json('settings.json').get('prefix', '!')

class KPTBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, intents=intents)

    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        print('✅ Commands cleared and synced!')

    async def on_ready(self):
        print(f'✅ Logged in as {self.user}')
        add_log('BOT_START', f'{self.user} came online')
        for guild in self.guilds:
            update_server_cache(guild)
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f'✅ Force synced to {guild.name}')
            except Exception as e:
                print(f'Sync error: {e}')
        msgs = get_msgs()
        status_text = msgs['general'].get('bot_status', 'your server | /help')
        status_type = msgs['general'].get('status_type', 'watching')
        type_map = {'watching': discord.ActivityType.watching, 'playing': discord.ActivityType.playing, 'listening': discord.ActivityType.listening, 'competing': discord.ActivityType.competing}
        await self.change_presence(activity=discord.Activity(type=type_map.get(status_type, discord.ActivityType.watching), name=status_text))

bot = KPTBot()
bot.remove_command('help')

# ---------- Permission Check ----------
def has_dashboard_access(member):
    """Check if member has admin or the configured dashboard role."""
    if member.guild_permissions.administrator: return True
    settings = load_json('settings.json')
    dashboard_role_id = settings.get('dashboard_role_id')
    if dashboard_role_id:
        return any(str(r.id) == str(dashboard_role_id) for r in member.roles)
    return False

def has_mod_permission(member, perm_key):
    """Check if member has a specific mod permission."""
    if member.guild_permissions.administrator: return True
    settings = load_json('settings.json')
    role_id = settings.get(f'perm_{perm_key}')
    if role_id:
        return any(str(r.id) == str(role_id) for r in member.roles)
    return False

# ---------- Groq AI ----------
def ask_groq(user_message: str) -> str:
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key: return "⚠️ AI isn't set up yet — please contact a staff member for help!"
    system_prompt = "You are KPT_BOT, the friendly AI assistant for the KaramPlaysThis Discord community. Professional, warm, energetic.\n\nRULES:\n1. Answer ANY question helpfully.\n2. KaramPlaysThis questions get extra detailed answers.\n3. General questions: answer fully, end with fun community plug.\n4. Hate speech, threats, harmful/illegal content: reply ONLY with '⚠️ I can\\'t help with that. Keep things respectful! Open a ticket if you need server support. 🎫'\n5. Under 280 words. Use Discord markdown."
    import json as _j
    payload = _j.dumps({"model":"llama3-8b-8192","messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_message}],"max_tokens":500,"temperature":0.7}).encode('utf-8')
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=payload, headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return _j.loads(resp.read().decode())['choices'][0]['message']['content']
    except Exception as e:
        print(f"Groq error: {e}")
        return "⚠️ I'm having a moment — try again shortly! Need urgent help? Open a ticket. 🎫"

# ---------- Events ----------
@bot.event
async def on_guild_update(before, after):
    update_server_cache(after)

@bot.event
async def on_guild_channel_create(channel):
    update_server_cache(channel.guild)

@bot.event
async def on_guild_channel_delete(channel):
    update_server_cache(channel.guild)

@bot.event
async def on_guild_role_create(role):
    update_server_cache(role.guild)

@bot.event
async def on_guild_role_delete(role):
    update_server_cache(role.guild)

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
            embed = discord.Embed(description=msg, color=color('welcome'))
            embed.set_author(name=m('welcome','author_text',server=guild.name), icon_url=member.display_avatar.url)
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
            embed = discord.Embed(description=msg, color=color('leave'))
            await channel.send(embed=embed)
    add_log('MEMBER_LEAVE', f'{member} left {guild.name}', guild.id)

@bot.event
async def on_message(message):
    if message.author.bot: return
    if isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            reply = ask_groq(message.content)
        short = message.content[:60]+'...' if len(message.content)>60 else message.content
        add_log('DM_AI', f'{message.author}: {short}')
        for i in range(0, len(reply), 2000): await message.channel.send(reply[i:i+2000])
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
        if settings.get('automod_badwords') and any(w in content for w in settings.get('bad_words',[])):
            await message.delete()
            await message.channel.send(m('automod','badword_msg',user=message.author.mention), delete_after=5)
            add_log('AUTOMOD_WORD', f'Deleted message from {message.author}', message.guild.id); deleted = True
        if not deleted and settings.get('automod_caps') and len(message.content)>8 and sum(1 for c in message.content if c.isupper())/len(message.content)>0.7:
            await message.delete()
            await message.channel.send(m('automod','caps_msg',user=message.author.mention), delete_after=5)
            add_log('AUTOMOD_CAPS', f'Deleted caps from {message.author}', message.guild.id); deleted = True
        if not deleted and settings.get('automod_links') and ('http://' in content or 'https://' in content or 'discord.gg/' in content):
            await message.delete()
            await message.channel.send(m('automod','link_msg',user=message.author.mention), delete_after=5)
            add_log('AUTOMOD_LINK', f'Deleted link from {message.author}', message.guild.id); deleted = True
        if deleted: return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions): await ctx.send(m('moderation','no_permission'))
    elif isinstance(error, commands.MemberNotFound): await ctx.send(m('moderation','member_not_found'))
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send(m('moderation','missing_argument',arg=error.param.name))
    elif isinstance(error, commands.CommandNotFound): pass

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or 'custom_id' not in interaction.data: return
    cid = interaction.data['custom_id']

    if cid.startswith('close_'):
        settings = load_json('settings.json')
        ticket_view_roles = settings.get('ticket_view_roles', [])
        can_close = interaction.user.guild_permissions.administrator
        if not can_close:
            can_close = any(str(r.id) in [str(x) for x in ticket_view_roles] for r in interaction.user.roles)
        if not can_close and str(interaction.user.id) in (interaction.channel.topic or ''):
            can_close = True
        if not can_close:
            return await interaction.response.send_message(m('tickets','close_perms'), ephemeral=True)
        modal = CloseTicketModal(channel_id=str(interaction.channel.id))
        await interaction.response.send_modal(modal)

    elif cid.startswith('claim_'):
        settings = load_json('settings.json')
        ticket_view_roles = settings.get('ticket_view_roles', [])
        can_claim = interaction.user.guild_permissions.administrator
        if not can_claim:
            can_claim = any(str(r.id) in [str(x) for x in ticket_view_roles] for r in interaction.user.roles)
        if not can_claim:
            return await interaction.response.send_message(m('tickets','claim_perms'), ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(description=m('tickets','claim_msg',user=interaction.user.mention), color=0x00FF88))
        add_log('TICKET_CLAIM', f'{interaction.user} claimed {interaction.channel.name}', interaction.guild.id)


# ---------- Close Ticket Modal ----------
class CloseTicketModal(discord.ui.Modal, title='🔒 Close Ticket'):
    def __init__(self, channel_id: str):
        super().__init__()
        self.channel_id = channel_id

    reason = discord.ui.TextInput(
        label='Why are you closing this ticket?',
        placeholder='e.g. Issue resolved, No response, Spam...',
        style=discord.TextStyle.long,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        close_reason = str(self.reason)
        channel = interaction.channel

        # Find the ticket opener from saved data
        tickets = load_json('tickets.json')
        opener_id = None
        for t in tickets.get('tickets', []):
            if t.get('channel_id') == str(channel.id):
                t['status'] = 'closed'
                t['close_reason'] = close_reason
                t['closed_by'] = str(interaction.user)
                opener_id = t.get('user_id')
                break
        save_json('tickets.json', tickets)

        # Send close message in ticket channel
        embed = discord.Embed(
            title='🔒 Ticket Closed',
            color=0xFF4466,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name='Closed by', value=interaction.user.mention, inline=True)
        embed.add_field(name='Reason', value=close_reason, inline=False)
        embed.set_footer(text='This channel will be deleted in 5 seconds')
        await interaction.response.send_message(embed=embed)

        # DM the ticket opener
        if opener_id:
            try:
                opener = await interaction.client.fetch_user(int(opener_id))
                dm_embed = discord.Embed(
                    title='🎫 Your Ticket Has Been Closed',
                    description=(
                        f'Your ticket in **{interaction.guild.name}** has been closed.\n\n'
                        f'**Closed by:** {interaction.user}\n'
                        f'**Reason:** {close_reason}\n\n'
                        f'> If you believe this was a false close, please open a new ticket and mention this reason.'
                    ),
                    color=0xFF4466,
                    timestamp=datetime.datetime.utcnow()
                )
                dm_embed.set_footer(text=f'KPT_BOT • {interaction.guild.name}')
                if interaction.guild.icon:
                    dm_embed.set_thumbnail(url=interaction.guild.icon.url)
                await opener.send(embed=dm_embed)
            except Exception as e:
                print(f'Could not DM ticket opener: {e}')

        add_log('TICKET_CLOSE', f'{interaction.user} closed {channel.name} | Reason: {close_reason}', interaction.guild.id)
        await asyncio.sleep(5)
        await channel.delete()

# ============================================================
# PREFIX COMMANDS
# ============================================================
@bot.command()
async def ping(ctx): await ctx.send(m('general','ping_msg',latency=round(bot.latency*1000)))

@bot.command()
async def info(ctx):
    embed = discord.Embed(title='KPT_BOT Info', color=color('ticket'))
    embed.add_field(name='Servers', value=len(bot.guilds))
    embed.add_field(name='Users', value=sum(g.member_count for g in bot.guilds))
    embed.add_field(name='Ping', value=f'{round(bot.latency*1000)}ms')
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=g.name, color=color('announce'))
    embed.add_field(name='Members', value=g.member_count)
    embed.add_field(name='Channels', value=len(g.channels))
    embed.add_field(name='Roles', value=len(g.roles))
    embed.add_field(name='Created', value=g.created_at.strftime('%b %d, %Y'))
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    prefix = get_prefix(bot, ctx.message)
    embed = discord.Embed(title='📖 KPT_BOT Commands', description=f'Prefix: `{prefix}` — Also supports `/` slash commands!', color=color('ticket'))
    embed.add_field(name='🛡️ Moderation', value=f'`{prefix}kick` `{prefix}ban` `{prefix}mute` `{prefix}unmute` `{prefix}warn` `{prefix}warnings` `{prefix}clearwarns` `{prefix}purge`', inline=False)
    embed.add_field(name='🎫 Tickets', value=f'`{prefix}ticket` `{prefix}closeticket`', inline=False)
    embed.add_field(name='🎉 Giveaways', value=f'`{prefix}giveaway` `{prefix}reroll`', inline=False)
    embed.add_field(name='📢 Other', value=f'`{prefix}announce` `{prefix}giverole` `{prefix}removerole` `{prefix}addcmd` `{prefix}delcmd` `{prefix}listcmds` `{prefix}serverinfo` `{prefix}ping` `{prefix}info`', inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason='No reason provided'):
    try: await member.send(m('moderation','kick_dm',server=ctx.guild.name,reason=reason))
    except: pass
    await member.kick(reason=reason)
    embed = discord.Embed(title=m('moderation','kick_title'), color=color('kick'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Reason',value=reason); embed.add_field(name='Moderator',value=str(ctx.author))
    await ctx.send(embed=embed); add_log('KICK', f'{ctx.author} kicked {member} | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason='No reason provided'):
    try: await member.send(m('moderation','ban_dm',server=ctx.guild.name,reason=reason))
    except: pass
    await member.ban(reason=reason)
    embed = discord.Embed(title=m('moderation','ban_title'), color=color('ban'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Reason',value=reason); embed.add_field(name='Moderator',value=str(ctx.author))
    await ctx.send(embed=embed); add_log('BAN', f'{ctx.author} banned {member} | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_name):
    banned = [entry async for entry in ctx.guild.bans()]
    for entry in banned:
        if str(entry.user)==user_name:
            await ctx.guild.unban(entry.user)
            await ctx.send(f'✅ Unbanned **{entry.user}**')
            add_log('UNBAN', f'{ctx.author} unbanned {entry.user}', ctx.guild.id); return
    await ctx.send('❌ User not found in ban list.')

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int=10, *, reason='No reason provided'):
    await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
    embed = discord.Embed(title=m('moderation','mute_title'), color=color('mute'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Duration',value=f'{minutes} minutes'); embed.add_field(name='Reason',value=reason)
    await ctx.send(embed=embed); add_log('MUTE', f'{ctx.author} muted {member} for {minutes}m | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(m('moderation','unmute_msg',user=str(member)))
    add_log('UNMUTE', f'{ctx.author} unmuted {member}', ctx.guild.id)

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason='No reason provided'):
    warns = load_json('warns.json'); uid = str(member.id)
    if uid not in warns: warns[uid]=[]
    warns[uid].append({'reason':reason,'by':str(ctx.author),'time':datetime.datetime.utcnow().isoformat()})
    save_json('warns.json', warns)
    embed = discord.Embed(title=m('moderation','warn_title'), color=color('warn'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Reason',value=reason); embed.add_field(name='Total Warns',value=len(warns[uid]))
    await ctx.send(embed=embed); add_log('WARN', f'{ctx.author} warned {member} | {reason}', ctx.guild.id)

@bot.command()
async def warnings(ctx, member: discord.Member):
    warns = load_json('warns.json'); user_warns = warns.get(str(member.id), [])
    if not user_warns: return await ctx.send(f'✅ **{member}** has no warnings.')
    embed = discord.Embed(title=f'⚠️ Warnings for {member}', color=color('warn'))
    for i,w in enumerate(user_warns,1): embed.add_field(name=f'Warn #{i}', value=f"Reason: {w['reason']}\nBy: {w['by']}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def clearwarns(ctx, member: discord.Member):
    warns = load_json('warns.json'); warns[str(member.id)]=[]
    save_json('warns.json', warns); await ctx.send(f'✅ Cleared all warnings for **{member}**.')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount+1)
    await ctx.send(m('moderation','purge_msg',amount=amount), delete_after=3)
    add_log('PURGE', f'{ctx.author} purged {amount} messages in #{ctx.channel.name}', ctx.guild.id)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def giverole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role: return await ctx.send(m('roles','role_not_found',role=role_name))
    await member.add_roles(role); await ctx.send(m('roles','give_msg',role=role.name,user=str(member)))
    add_log('ROLE_GIVE', f'{ctx.author} gave {role.name} to {member}', ctx.guild.id)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role: return await ctx.send(m('roles','role_not_found',role=role_name))
    await member.remove_roles(role); await ctx.send(m('roles','remove_msg',role=role.name,user=str(member)))
    add_log('ROLE_REMOVE', f'{ctx.author} removed {role.name} from {member}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def announce(ctx, channel: discord.TextChannel, *, message: str):
    embed = discord.Embed(description=message, color=color('announce'), timestamp=datetime.datetime.utcnow())
    embed.set_author(name='📢 Announcement', icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f'Announced by {ctx.author}')
    await channel.send(embed=embed); await ctx.send(f'✅ Sent to {channel.mention}')
    add_log('ANNOUNCE', f'{ctx.author} announced in #{channel.name}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, minutes: int, winners: int, *, prize: str):
    end_time = datetime.datetime.utcnow()+datetime.timedelta(minutes=minutes)
    gm = get_msgs()['giveaway']
    embed = discord.Embed(title=gm.get('title','🎉 GIVEAWAY 🎉'), description=f'**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>\n\n{gm.get("enter_instruction","React with 🎉 to enter!")}', color=color('giveaway'), timestamp=end_time)
    embed.set_footer(text=gm.get('footer','Hosted by {host}').replace('{host}',str(ctx.author)))
    msg = await ctx.send(embed=embed); await msg.add_reaction('🎉')
    # Save active giveaway
    gws = load_json('giveaways.json')
    if 'active' not in gws: gws['active'] = []
    gws['active'].append({'message_id':str(msg.id),'channel_id':str(ctx.channel.id),'prize':prize,'winners':winners,'end_time':end_time.isoformat(),'host':str(ctx.author),'status':'active'})
    save_json('giveaways.json', gws)
    add_log('GIVEAWAY_START', f'{ctx.author} started: {prize}', ctx.guild.id)
    await asyncio.sleep(minutes*60)
    await _end_giveaway(ctx.channel, msg.id, winners, prize, str(ctx.author), ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def reroll(ctx, message_id: int, winners: int=1):
    try:
        msg = await ctx.channel.fetch_message(message_id)
        reaction = discord.utils.get(msg.reactions, emoji='🎉')
        users = [u async for u in reaction.users() if not u.bot]
        winner_list = random.sample(users, min(winners,len(users)))
        await ctx.send(f'🎉 New winner(s): {", ".join(w.mention for w in winner_list)}!')
    except: await ctx.send('❌ Could not find that message.')

@bot.command()
async def ticket(ctx, *, reason='General Support'):
    await _open_ticket(ctx.guild, ctx.author, ctx.channel, reason)

@bot.command()
async def closeticket(ctx):
    if 'ticket-' not in ctx.channel.name: return await ctx.send(m('tickets','not_ticket_channel'))
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label='🔒 Close Ticket', style=discord.ButtonStyle.danger, custom_id=f'close_{ctx.channel.id}'))
    await ctx.send('Click below to close this ticket — you will be asked for a reason.', view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def addcmd(ctx, name: str, *, response: str):
    cmds = load_json('custom_commands.json'); cmds[name.lower()] = response
    save_json('custom_commands.json', cmds)
    await ctx.send(f'✅ Custom command `{get_prefix(bot,ctx.message)}{name}` created!')
    add_log('CUSTOM_CMD_ADD', f'{ctx.author} added command: {name}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def delcmd(ctx, name: str):
    cmds = load_json('custom_commands.json')
    if name.lower() in cmds:
        del cmds[name.lower()]; save_json('custom_commands.json', cmds); await ctx.send(f'✅ Deleted `{name}`.')
    else: await ctx.send(f'❌ Command `{name}` not found.')

@bot.command()
async def listcmds(ctx):
    cmds = load_json('custom_commands.json'); prefix = get_prefix(bot, ctx.message)
    if not cmds: return await ctx.send('No custom commands yet.')
    embed = discord.Embed(title='Custom Commands', color=color('ticket'))
    for name, resp in cmds.items(): embed.add_field(name=f'`{prefix}{name}`', value=resp[:50], inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, prefix: str):
    settings = load_json('settings.json'); settings['prefix'] = prefix
    save_json('settings.json', settings); await ctx.send(f'✅ Prefix changed to `{prefix}`')
    add_log('SETTINGS', f'{ctx.author} changed prefix to {prefix}', ctx.guild.id)

# ---------- Giveaway Helper ----------
async def _end_giveaway(channel, message_id, winners_count, prize, host, guild_id):
    try:
        msg = await channel.fetch_message(message_id)
        reaction = discord.utils.get(msg.reactions, emoji='🎉')
        users = [u async for u in reaction.users() if not u.bot]
        gm = get_msgs()['giveaway']
        if not users:
            await channel.send(gm.get('no_entries','Nobody entered!'))
        else:
            winner_list = random.sample(users, min(winners_count,len(users)))
            winner_mentions = ', '.join(w.mention for w in winner_list)
            await channel.send(embed=discord.Embed(title=gm.get('end_title','🎉 Giveaway Ended!'), description=f'**Prize:** {prize}\n**Winner(s):** {winner_mentions}', color=color('giveaway')))
            await channel.send(gm.get('winners_msg','Congratulations {winners}! You won **{prize}**! 🎉').replace('{winners}',winner_mentions).replace('{prize}',prize))
            add_log('GIVEAWAY_END', f'Giveaway: {prize} | Winners: {winner_mentions}', guild_id)
        # Update status
        gws = load_json('giveaways.json')
        for gw in gws.get('active',[]):
            if gw.get('message_id')==str(message_id): gw['status']='ended'
        save_json('giveaways.json', gws)
    except Exception as e:
        print(f"Giveaway end error: {e}")

# ============================================================
# SLASH COMMANDS
# ============================================================
@bot.tree.command(name='ping', description="Check the bot's latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(m('general','ping_msg',latency=round(bot.latency*1000)))

@bot.tree.command(name='info', description='Show bot information')
async def slash_info(interaction: discord.Interaction):
    embed = discord.Embed(title='KPT_BOT Info', color=color('ticket'))
    embed.add_field(name='Servers', value=len(bot.guilds))
    embed.add_field(name='Users', value=sum(g.member_count for g in bot.guilds))
    embed.add_field(name='Ping', value=f'{round(bot.latency*1000)}ms')
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='serverinfo', description='Show server information')
async def slash_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=g.name, color=color('announce'))
    embed.add_field(name='Members', value=g.member_count)
    embed.add_field(name='Channels', value=len(g.channels))
    embed.add_field(name='Roles', value=len(g.roles))
    embed.add_field(name='Created', value=g.created_at.strftime('%b %d, %Y'))
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='help', description='Show all KPT_BOT commands')
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title='📖 KPT_BOT Commands', description='Use `/` or `!` for commands', color=color('ticket'))
    embed.add_field(name='🛡️ Moderation', value='`/kick` `/ban` `/mute` `/unmute` `/warn` `/warnings` `/purge`', inline=False)
    embed.add_field(name='🎫 Tickets', value='`/ticket` `/closeticket` `/ticketpanel`', inline=False)
    embed.add_field(name='🎉 Giveaways', value='`/giveaway` `/reroll`', inline=False)
    embed.add_field(name='📢 Other', value='`/announce` `/giverole` `/removerole` `/serverinfo` `/ping` `/info`', inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='kick', description='Kick a member from the server')
@app_commands.describe(member='The member to kick', reason='Reason for the kick')
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str='No reason provided'):
    if not interaction.user.guild_permissions.kick_members: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    try: await member.send(m('moderation','kick_dm',server=interaction.guild.name,reason=reason))
    except: pass
    await member.kick(reason=reason)
    embed = discord.Embed(title=m('moderation','kick_title'), color=color('kick'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Reason',value=reason); embed.add_field(name='Moderator',value=str(interaction.user))
    await interaction.followup.send(embed=embed); add_log('KICK', f'{interaction.user} kicked {member} | {reason}', interaction.guild.id)

@bot.tree.command(name='ban', description='Ban a member from the server')
@app_commands.describe(member='The member to ban', reason='Reason for the ban')
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str='No reason provided'):
    if not interaction.user.guild_permissions.ban_members: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    try: await member.send(m('moderation','ban_dm',server=interaction.guild.name,reason=reason))
    except: pass
    await member.ban(reason=reason)
    embed = discord.Embed(title=m('moderation','ban_title'), color=color('ban'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Reason',value=reason); embed.add_field(name='Moderator',value=str(interaction.user))
    await interaction.followup.send(embed=embed); add_log('BAN', f'{interaction.user} banned {member} | {reason}', interaction.guild.id)

@bot.tree.command(name='mute', description='Timeout (mute) a member')
@app_commands.describe(member='The member to mute', minutes='Duration in minutes', reason='Reason')
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int=10, reason: str='No reason provided'):
    if not interaction.user.guild_permissions.moderate_members: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
    embed = discord.Embed(title=m('moderation','mute_title'), color=color('mute'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Duration',value=f'{minutes} minutes'); embed.add_field(name='Reason',value=reason)
    await interaction.followup.send(embed=embed); add_log('MUTE', f'{interaction.user} muted {member} for {minutes}m | {reason}', interaction.guild.id)

@bot.tree.command(name='unmute', description='Remove a timeout from a member')
@app_commands.describe(member='The member to unmute')
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    await member.timeout(None)
    await interaction.followup.send(m('moderation','unmute_msg',user=str(member)))
    add_log('UNMUTE', f'{interaction.user} unmuted {member}', interaction.guild.id)

@bot.tree.command(name='warn', description='Warn a member')
@app_commands.describe(member='The member to warn', reason='Reason for the warning')
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str='No reason provided'):
    if not interaction.user.guild_permissions.kick_members: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    warns = load_json('warns.json'); uid = str(member.id)
    if uid not in warns: warns[uid]=[]
    warns[uid].append({'reason':reason,'by':str(interaction.user),'time':datetime.datetime.utcnow().isoformat()})
    save_json('warns.json', warns)
    embed = discord.Embed(title=m('moderation','warn_title'), color=color('warn'), timestamp=datetime.datetime.utcnow())
    embed.add_field(name='User',value=str(member)); embed.add_field(name='Reason',value=reason); embed.add_field(name='Total Warns',value=len(warns[uid]))
    await interaction.followup.send(embed=embed); add_log('WARN', f'{interaction.user} warned {member} | {reason}', interaction.guild.id)

@bot.tree.command(name='warnings', description='View warnings for a member')
@app_commands.describe(member='The member to check')
async def slash_warnings(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    warns = load_json('warns.json'); user_warns = warns.get(str(member.id),[])
    if not user_warns: return await interaction.followup.send(f'✅ **{member}** has no warnings.')
    embed = discord.Embed(title=f'⚠️ Warnings for {member}', color=color('warn'))
    for i,w in enumerate(user_warns,1): embed.add_field(name=f'Warn #{i}', value=f"Reason: {w['reason']}\nBy: {w['by']}", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='purge', description='Delete a number of messages')
@app_commands.describe(amount='Number of messages to delete')
async def slash_purge(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.send_message(f'🧹 Deleting {amount} messages...', ephemeral=True)
    await interaction.channel.purge(limit=amount)
    add_log('PURGE', f'{interaction.user} purged {amount} in #{interaction.channel.name}', interaction.guild.id)

@bot.tree.command(name='ticket', description='Open a support ticket')
async def slash_ticket(interaction: discord.Interaction):
    """Shows a dropdown to pick ticket category — no panel needed."""
    cfg = get_panel_config()
    cats = cfg.get('categories', [])[:25]
    if not cats:
        await interaction.response.defer(ephemeral=True)
        channel = await _open_ticket(interaction.guild, interaction.user, None, 'General Support')
        await interaction.followup.send(m('tickets','open_confirm',channel=channel.mention), ephemeral=True)
        return

    # Build ephemeral dropdown view
    options = [
        discord.SelectOption(
            label=c['label'][:100],
            value=c['id'],
            description=c.get('description','')[:100]
        ) for c in cats
    ]

    class TicketSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)

        @discord.ui.select(
            placeholder=cfg.get('dropdown_placeholder', '📂 Select a ticket category...'),
            min_values=1, max_values=1,
            options=options
        )
        async def select_callback(self, interaction2: discord.Interaction, select: discord.ui.Select):
            cat_id = select.values[0]
            cats_map = {c['id']: c for c in cats}
            category = cats_map.get(cat_id)
            if category:
                await interaction2.response.send_modal(build_modal(category)())
            else:
                await interaction2.response.send_message('❌ Category not found.', ephemeral=True)

    embed = discord.Embed(
        title='🎫 Open a Support Ticket',
        description='Select a category below that best describes your issue.\nYou will then be asked a few quick questions.',
        color=0x5865F2
    )
    embed.set_footer(text='KPT_BOT Ticket System')
    await interaction.response.send_message(embed=embed, view=TicketSelectView(), ephemeral=True)

@bot.tree.command(name='closeticket', description='Close the current ticket channel')
async def slash_closeticket(interaction: discord.Interaction):
    if 'ticket-' not in interaction.channel.name:
        return await interaction.response.send_message(m('tickets','not_ticket_channel'), ephemeral=True)
    settings = load_json('settings.json')
    ticket_view_roles = settings.get('ticket_view_roles', [])
    can_close = interaction.user.guild_permissions.administrator
    if not can_close:
        can_close = any(str(r.id) in [str(x) for x in ticket_view_roles] for r in interaction.user.roles)
    if not can_close and str(interaction.user.id) in (interaction.channel.topic or ''):
        can_close = True
    if not can_close:
        return await interaction.response.send_message(m('tickets','close_perms'), ephemeral=True)
    await interaction.response.send_modal(CloseTicketModal(channel_id=str(interaction.channel.id)))

@bot.tree.command(name='giverole', description='Give a role to a member')
@app_commands.describe(member='The member', role='The role to give')
async def slash_giverole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    await member.add_roles(role)
    await interaction.followup.send(m('roles','give_msg',role=role.name,user=str(member)))
    add_log('ROLE_GIVE', f'{interaction.user} gave {role.name} to {member}', interaction.guild.id)

@bot.tree.command(name='removerole', description='Remove a role from a member')
@app_commands.describe(member='The member', role='The role to remove')
async def slash_removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    await member.remove_roles(role)
    await interaction.followup.send(m('roles','remove_msg',role=role.name,user=str(member)))
    add_log('ROLE_REMOVE', f'{interaction.user} removed {role.name} from {member}', interaction.guild.id)

@bot.tree.command(name='announce', description='Send an announcement to a channel')
@app_commands.describe(channel='Channel to announce in', message='The announcement message')
async def slash_announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(description=message, color=color('announce'), timestamp=datetime.datetime.utcnow())
    embed.set_author(name='📢 Announcement', icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f'Announced by {interaction.user}')
    await channel.send(embed=embed); await interaction.followup.send(f'✅ Sent to {channel.mention}!', ephemeral=True)
    add_log('ANNOUNCE', f'{interaction.user} announced in #{channel.name}', interaction.guild.id)

@bot.tree.command(name='giveaway', description='Start a giveaway')
@app_commands.describe(minutes='Duration in minutes', winners='Number of winners', prize="What you're giving away")
async def slash_giveaway(interaction: discord.Interaction, minutes: int, winners: int, prize: str):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message(m('moderation','no_permission'), ephemeral=True)
    await interaction.response.defer()
    end_time = datetime.datetime.utcnow()+datetime.timedelta(minutes=minutes)
    gm = get_msgs()['giveaway']
    embed = discord.Embed(title=gm.get('title','🎉 GIVEAWAY 🎉'), description=f'**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>\n\n{gm.get("enter_instruction","React with 🎉 to enter!")}', color=color('giveaway'), timestamp=end_time)
    embed.set_footer(text=gm.get('footer','Hosted by {host}').replace('{host}',str(interaction.user)))
    msg = await interaction.followup.send(embed=embed); await msg.add_reaction('🎉')
    gws = load_json('giveaways.json')
    if 'active' not in gws: gws['active'] = []
    gws['active'].append({'message_id':str(msg.id),'channel_id':str(interaction.channel.id),'prize':prize,'winners':winners,'end_time':end_time.isoformat(),'host':str(interaction.user),'status':'active'})
    save_json('giveaways.json', gws)
    add_log('GIVEAWAY_START', f'{interaction.user} started: {prize}', interaction.guild.id)
    await asyncio.sleep(minutes*60)
    await _end_giveaway(interaction.channel, msg.id, winners, prize, str(interaction.user), interaction.guild.id)

# ============================================================
# TICKET PANEL SYSTEM
# ============================================================
DEFAULT_PANEL = {
    'panel_title':'🎫 KaramPlaysThis Support','panel_description':'**Need help? Open a ticket below!**\n\nSelect a category from the dropdown to get started.','panel_footer':'KPT_BOT Ticket System • One ticket per issue please!','panel_color':'5865F2','dropdown_placeholder':'📂 Select a ticket category...',
    'categories':[
        {'id':'general','label':'🙋 General Support','description':'General questions or server help','slug':'general','color':'5865F2','modal_title':'🙋 General Support','fields':[{'label':'What do you need help with?','placeholder':'Brief summary...','style':'short','required':True,'max_length':100},{'label':'Please describe in detail','placeholder':'Full details...','style':'long','required':True,'max_length':1000},{'label':'What have you already tried?','placeholder':'e.g. Checked FAQ...','style':'short','required':False,'max_length':200}]},
        {'id':'stream','label':'🔴 Stream Problem','description':'Issues watching streams','slug':'stream','color':'FF4466','modal_title':'🔴 Stream Problem','fields':[{'label':'What is the stream problem?','placeholder':'e.g. Buffering, no audio...','style':'short','required':True,'max_length':100},{'label':'Which platform?','placeholder':'e.g. Twitch, YouTube...','style':'short','required':True,'max_length':50},{'label':'What device?','placeholder':'e.g. PC, Phone...','style':'short','required':True,'max_length':50},{'label':'Extra details?','placeholder':'Error messages, when it started...','style':'long','required':False,'max_length':500}]},
        {'id':'report','label':'🚨 Report a Player','description':'Report a member for rule breaking','slug':'report','color':'FF9900','modal_title':'🚨 Report a Player','fields':[{'label':'Username of the player','placeholder':'e.g. BadUser#1234','style':'short','required':True,'max_length':100},{'label':'Reason for report','placeholder':'e.g. Harassment, spam...','style':'short','required':True,'max_length':100},{'label':'What happened?','placeholder':'Full situation details...','style':'long','required':True,'max_length':1000},{'label':'Do you have evidence?','placeholder':'Yes/No — attach in ticket','style':'short','required':False,'max_length':200}]},
        {'id':'partner','label':'🤝 Partnership','description':'Partnership or collab requests','slug':'partner','color':'00d4ff','modal_title':'🤝 Partnership Request','fields':[{'label':'Your brand name','placeholder':'e.g. YourBrand','style':'short','required':True,'max_length':100},{'label':'Platform & follower count','placeholder':'e.g. YouTube — 5,000 subs','style':'short','required':True,'max_length':100},{'label':'What are you proposing?','placeholder':'Describe your idea...','style':'long','required':True,'max_length':1000},{'label':'Your social links','placeholder':'e.g. youtube.com/...','style':'short','required':True,'max_length':200}]},
        {'id':'other','label':'❓ Other','description':'Anything else not listed above','slug':'other','color':'8892b0','modal_title':'❓ Other','fields':[{'label':'Subject','placeholder':'Brief subject...','style':'short','required':True,'max_length':100},{'label':'Full details','placeholder':'Explain in full detail...','style':'long','required':True,'max_length':1000}]},
    ]
}

def get_panel_config():
    cfg = load_json('panel_config.json')
    return cfg if cfg else DEFAULT_PANEL

def build_modal(category: dict):
    fields_cfg = category.get('fields', [])[:5]
    class DynamicModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(title=category.get('modal_title','Open Ticket')[:45])
            for i,f in enumerate(fields_cfg):
                style = discord.TextStyle.long if f.get('style')=='long' else discord.TextStyle.short
                item = discord.ui.TextInput(label=f['label'][:45], placeholder=f.get('placeholder','')[:100], style=style, required=f.get('required',True), max_length=min(f.get('max_length',1000),4000))
                setattr(self, f'field_{i}', item); self.add_item(item)
        async def on_submit(self, interaction: discord.Interaction):
            filled = {}
            for i,f in enumerate(fields_cfg):
                val = str(getattr(self, f'field_{i}'))
                filled[f['label']] = val if val else 'Not provided'
            await _create_ticket_channel(interaction, category.get('label','Ticket'), category.get('slug','ticket'), filled, category.get('color','5865F2'))
    return DynamicModal

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        cfg = get_panel_config(); cats = cfg.get('categories',[])[:25]
        options = [discord.SelectOption(label=c['label'][:100], value=c['id'], description=c.get('description','')[:100]) for c in cats]
        super().__init__(placeholder=cfg.get('dropdown_placeholder','📂 Select a category...')[:150], min_values=1, max_values=1, options=options, custom_id='ticket_dropdown')
    async def callback(self, interaction: discord.Interaction):
        cfg = get_panel_config(); cats = {c['id']:c for c in cfg.get('categories',[])}
        category = cats.get(self.values[0])
        if category: await interaction.response.send_modal(build_modal(category)())
        else: await interaction.response.send_message('❌ Category not found.', ephemeral=True)

class TicketPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(TicketDropdown())

async def _create_ticket_channel(interaction, category_name, slug, fields, color_hex='5865F2'):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild; user = interaction.user
    settings = load_json('settings.json'); tickets = load_json('tickets.json')
    if 'count' not in tickets: tickets['count']=0
    tickets['count']+=1; ticket_num=tickets['count']
    channel_name = f'ticket-{ticket_num:04d}-{slug[:15]}'
    category_id = settings.get('ticket_category')
    category = guild.get_channel(int(category_id)) if category_id else None
    ticket_view_roles = settings.get('ticket_view_roles', [])
    overwrites = {guild.default_role:discord.PermissionOverwrite(read_messages=False), user:discord.PermissionOverwrite(read_messages=True,send_messages=True,attach_files=True), guild.me:discord.PermissionOverwrite(read_messages=True,send_messages=True,manage_channels=True)}
    # Give access to all ticket viewer roles
    role_mentions = []
    for rid in ticket_view_roles:
        role = guild.get_role(int(rid))
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True,send_messages=True)
            role_mentions.append(role.mention)
    # Admins always get access
    for role in guild.roles:
        if role.permissions.administrator: overwrites[role]=discord.PermissionOverwrite(read_messages=True,send_messages=True)
    channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category, topic=f'Ticket #{ticket_num:04d} | {category_name} | {user.id} | {user}')
    if 'tickets' not in tickets: tickets['tickets']=[]
    tickets['tickets'].insert(0,{'id':ticket_num,'user':str(user),'user_id':str(user.id),'category':category_name,'channel':channel_name,'channel_id':str(channel.id),'status':'open','time':datetime.datetime.utcnow().isoformat()})
    save_json('tickets.json', tickets)
    try: col = int(color_hex.lstrip('#'),16)
    except: col=0x5865F2
    embed = discord.Embed(title=f'🎫 Ticket #{ticket_num:04d} — {category_name}', color=col, timestamp=datetime.datetime.utcnow())
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    embed.add_field(name='📋 Category',value=category_name,inline=True); embed.add_field(name='👤 Opened By',value=user.mention,inline=True); embed.add_field(name='\u200b',value='\u200b',inline=True)
    for label,value in fields.items(): embed.add_field(name=f'❯ {label}',value=str(value)[:1024],inline=False)
    embed.set_footer(text=m('tickets','ticket_footer'))
    btn_view = discord.ui.View(timeout=None)
    btn_view.add_item(discord.ui.Button(label='🔒 Close Ticket',style=discord.ButtonStyle.danger,custom_id=f'close_{channel.id}'))
    btn_view.add_item(discord.ui.Button(label='✋ Claim',style=discord.ButtonStyle.secondary,custom_id=f'claim_{channel.id}'))
    mention_str = user.mention + (' ' + ' '.join(role_mentions) if role_mentions else '')
    await channel.send(mention_str, embed=embed, view=btn_view)
    await interaction.followup.send(m('tickets','open_confirm',channel=channel.mention), ephemeral=True)
    add_log('TICKET_OPEN', f'{user} opened ticket #{ticket_num:04d}: {category_name}', guild.id)
    return channel

async def _open_ticket(guild, user, reply_channel, reason):
    settings=load_json('settings.json'); tickets=load_json('tickets.json')
    if 'count' not in tickets: tickets['count']=0
    tickets['count']+=1; ticket_num=tickets['count']
    channel_name=f'ticket-{ticket_num:04d}-{reason.lower().replace(" ","-")[:15]}'
    category_id=settings.get('ticket_category'); category=guild.get_channel(int(category_id)) if category_id else None
    ticket_view_roles = settings.get('ticket_view_roles', [])
    overwrites={guild.default_role:discord.PermissionOverwrite(read_messages=False),user:discord.PermissionOverwrite(read_messages=True,send_messages=True,attach_files=True),guild.me:discord.PermissionOverwrite(read_messages=True,send_messages=True,manage_channels=True)}
    role_mentions = []
    for rid in ticket_view_roles:
        role = guild.get_role(int(rid))
        if role:
            overwrites[role]=discord.PermissionOverwrite(read_messages=True,send_messages=True)
            role_mentions.append(role.mention)
    for role in guild.roles:
        if role.permissions.administrator: overwrites[role]=discord.PermissionOverwrite(read_messages=True,send_messages=True)
    channel=await guild.create_text_channel(channel_name,overwrites=overwrites,category=category,topic=f'Ticket #{ticket_num:04d} | {user.id} | {user} | {reason}')
    if 'tickets' not in tickets: tickets['tickets']=[]
    tickets['tickets'].insert(0,{'id':ticket_num,'user':str(user),'user_id':str(user.id),'category':reason,'channel':channel_name,'channel_id':str(channel.id),'status':'open','time':datetime.datetime.utcnow().isoformat()})
    save_json('tickets.json',tickets)
    embed=discord.Embed(title=f'🎫 Ticket #{ticket_num:04d}',description=f'**Topic:** {reason}\n**Opened by:** {user.mention}\n\nSupport will be with you shortly!',color=color('ticket'),timestamp=datetime.datetime.utcnow())
    embed.set_footer(text=m('tickets','ticket_footer'))
    view=discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label='🔒 Close Ticket',style=discord.ButtonStyle.danger,custom_id=f'close_{channel.id}'))
    view.add_item(discord.ui.Button(label='✋ Claim',style=discord.ButtonStyle.secondary,custom_id=f'claim_{channel.id}'))
    mention_str = str(user.mention) + (' ' + ' '.join(role_mentions) if role_mentions else '')
    await channel.send(mention_str,embed=embed,view=view)
    add_log('TICKET_OPEN',f'{user} opened ticket #{ticket_num:04d}: {reason}',guild.id)
    return channel

@bot.tree.command(name='ticketpanel', description='Post the ticket panel in this channel')
async def slash_ticketpanel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message('❌ Admins only.', ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    cfg = get_panel_config()
    try: col = int(cfg.get('panel_color','5865F2').lstrip('#'),16)
    except: col = 0x5865F2
    embed = discord.Embed(title=cfg.get('panel_title','🎫 Support'), description=cfg.get('panel_description','Open a ticket below!'), color=col, timestamp=datetime.datetime.utcnow())
    embed.set_footer(text=cfg.get('panel_footer','KPT_BOT Ticket System'))
    if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
    await interaction.channel.send(embed=embed, view=TicketPanelView())
    await interaction.followup.send('✅ Ticket panel posted!', ephemeral=True)
    add_log('TICKET_PANEL', f'{interaction.user} posted panel in #{interaction.channel.name}', interaction.guild.id)

# ============================================================
# PENDING ACTIONS — Dashboard -> Bot bridge (checks every 1s)
# ============================================================
from discord.ext import tasks

@tasks.loop(seconds=1)
async def process_pending():
    pending = load_json('pending_actions.json')
    actions = pending.get('actions', [])
    if not actions: return
    remaining = []
    for action in actions:
        try:
            atype = action.get('type')
            data = action.get('data', {})
            guild = bot.guilds[0] if bot.guilds else None
            if not guild: remaining.append(action); continue
            if atype == 'announce':
                ch = guild.get_channel(int(data.get('channel_id', 0)))
                if ch:
                    embed = discord.Embed(description=data.get('message',''), color=color('announce'), timestamp=datetime.datetime.utcnow())
                    embed.set_author(name='📢 Announcement', icon_url=guild.icon.url if guild.icon else None)
                    embed.set_footer(text='Posted via Dashboard')
                    await ch.send(embed=embed)
                    add_log('ANNOUNCE', f'Dashboard posted in #{ch.name}', guild.id)
            elif atype == 'giveaway':
                ch = guild.get_channel(int(data.get('channel_id', 0)))
                if ch:
                    minutes = int(data.get('minutes', 60))
                    winners = int(data.get('winners', 1))
                    prize = data.get('prize', 'Prize')
                    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
                    gm = get_msgs()['giveaway']
                    embed = discord.Embed(title=gm.get('title','🎉 GIVEAWAY 🎉'), description=f'**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>\n\n{gm.get("enter_instruction","React with 🎉 to enter!")}', color=color('giveaway'), timestamp=end_time)
                    embed.set_footer(text=gm.get('footer','Hosted by {host}').replace('{host}','Dashboard'))
                    msg = await ch.send(embed=embed)
                    await msg.add_reaction('🎉')
                    gws = load_json('giveaways.json')
                    if 'active' not in gws: gws['active'] = []
                    gws['active'].append({'message_id':str(msg.id),'channel_id':str(ch.id),'prize':prize,'winners':winners,'host':'Dashboard','end_time':end_time.isoformat(),'status':'active'})
                    save_json('giveaways.json', gws)
                    add_log('GIVEAWAY_START', f'Dashboard started: {prize}', guild.id)
            elif atype == 'ticketpanel':
                ch = guild.get_channel(int(data.get('channel_id', 0)))
                if ch:
                    cfg = get_panel_config()
                    try: col = int(cfg.get('panel_color','5865F2').lstrip('#'),16)
                    except: col = 0x5865F2
                    embed = discord.Embed(title=cfg.get('panel_title','🎫 Support'), description=cfg.get('panel_description','Open a ticket below!'), color=col, timestamp=datetime.datetime.utcnow())
                    embed.set_footer(text=cfg.get('panel_footer','KPT_BOT Ticket System'))
                    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
                    await ch.send(embed=embed, view=TicketPanelView())
                    add_log('TICKET_PANEL', f'Dashboard posted panel in #{ch.name}', guild.id)
        except Exception as e:
            print(f'Pending action error: {e}')
    pending['actions'] = remaining
    save_json('pending_actions.json', pending)

@bot.event
async def on_ready_tasks():
    if not process_pending.is_running():
        process_pending.start()

bot.run(os.getenv('DISCORD_TOKEN'))
