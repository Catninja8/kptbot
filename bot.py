import discord
from discord.ext import commands
import os
import json
import datetime
import random
import asyncio
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

# ---------- Intents & Bot ----------
intents = discord.Intents.all()

def get_prefix(bot, message):
    settings = load_json('settings.json')
    return settings.get('prefix', '!')

bot = commands.Bot(command_prefix=get_prefix, intents=intents)

# ---------- Events ----------
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    add_log('BOT_START', f'{bot.user} came online')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="your server 👀"))

@bot.event
async def on_member_join(member):
    settings = load_json('settings.json')
    guild = member.guild

    # Welcome message
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

    # Auto role
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

    settings = load_json('settings.json')

    # Custom commands
    custom_cmds = load_json('custom_commands.json')
    prefix = settings.get('prefix', '!')
    if message.content.startswith(prefix):
        cmd_name = message.content[len(prefix):].split()[0].lower()
        if cmd_name in custom_cmds:
            await message.channel.send(custom_cmds[cmd_name])
            return

    # Auto-mod
    if settings.get('automod_enabled'):
        content = message.content.lower()
        deleted = False

        # Bad words
        if settings.get('automod_badwords'):
            bad_words = settings.get('bad_words', [])
            if any(w in content for w in bad_words):
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} watch your language!', delete_after=5)
                add_log('AUTOMOD_WORD', f'Deleted message from {message.author}', message.guild.id)
                deleted = True

        # Caps filter
        if not deleted and settings.get('automod_caps'):
            if len(message.content) > 8 and sum(1 for c in message.content if c.isupper()) / len(message.content) > 0.7:
                await message.delete()
                await message.channel.send(f'⚠️ {message.author.mention} please don\'t use excessive caps!', delete_after=5)
                add_log('AUTOMOD_CAPS', f'Deleted caps message from {message.author}', message.guild.id)
                deleted = True

        # Link filter
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
    embed.set_footer(text='KPT_BOT Dashboard • kptbot')
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

# ---------- Moderation ----------
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason='No reason provided'):
    await member.kick(reason=reason)
    embed = discord.Embed(title='👢 Member Kicked', color=0xFF4466)
    embed.add_field(name='User', value=str(member))
    embed.add_field(name='Reason', value=reason)
    embed.add_field(name='Moderator', value=str(ctx.author))
    await ctx.send(embed=embed)
    add_log('KICK', f'{ctx.author} kicked {member} | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason='No reason provided'):
    await member.ban(reason=reason)
    embed = discord.Embed(title='🔨 Member Banned', color=0xFF0000)
    embed.add_field(name='User', value=str(member))
    embed.add_field(name='Reason', value=reason)
    embed.add_field(name='Moderator', value=str(ctx.author))
    await ctx.send(embed=embed)
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
    embed = discord.Embed(title='🔇 Member Muted', color=0xFFCC00)
    embed.add_field(name='User', value=str(member))
    embed.add_field(name='Duration', value=f'{minutes} minutes')
    embed.add_field(name='Reason', value=reason)
    await ctx.send(embed=embed)
    add_log('MUTE', f'{ctx.author} muted {member} for {minutes}m | {reason}', ctx.guild.id)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f'🔊 **{member}** has been unmuted.')
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
    embed = discord.Embed(title='⚠️ Member Warned', color=0xFF9900)
    embed.add_field(name='User', value=str(member))
    embed.add_field(name='Reason', value=reason)
    embed.add_field(name='Total Warns', value=len(warns[uid]))
    await ctx.send(embed=embed)
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

# ---------- Roles ----------
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

# ---------- Announcements ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def announce(ctx, channel: discord.TextChannel, *, message: str):
    embed = discord.Embed(description=message, color=0x00d4ff, timestamp=datetime.datetime.utcnow())
    embed.set_author(name='📢 Announcement', icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f'Announced by {ctx.author}')
    await channel.send(embed=embed)
    await ctx.send(f'✅ Announcement sent to {channel.mention}')
    add_log('ANNOUNCE', f'{ctx.author} announced in #{channel.name}', ctx.guild.id)

# ---------- Giveaways ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, minutes: int, winners: int, *, prize: str):
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
    embed = discord.Embed(
        title='🎉 GIVEAWAY 🎉',
        description=f'**Prize:** {prize}\n\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>\n\nReact with 🎉 to enter!',
        color=0x00FF88,
        timestamp=end_time
    )
    embed.set_footer(text=f'Ends at • Hosted by {ctx.author}')
    msg = await ctx.send(embed=embed)
    await msg.add_reaction('🎉')
    add_log('GIVEAWAY_START', f'{ctx.author} started giveaway: {prize} ({winners} winners, {minutes}m)', ctx.guild.id)

    await asyncio.sleep(minutes * 60)

    msg = await ctx.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji='🎉')
    users = [u async for u in reaction.users() if not u.bot]

    if not users:
        await ctx.send('🎉 Giveaway ended but no one entered!')
        return

    actual_winners = min(winners, len(users))
    winner_list = random.sample(users, actual_winners)
    winner_mentions = ', '.join(w.mention for w in winner_list)

    embed2 = discord.Embed(title='🎉 Giveaway Ended!', description=f'**Prize:** {prize}\n**Winner(s):** {winner_mentions}', color=0x00FF88)
    await ctx.send(embed=embed2)
    await ctx.send(f'Congratulations {winner_mentions}! You won **{prize}**! 🎉')
    add_log('GIVEAWAY_END', f'Giveaway ended: {prize} | Winners: {[str(w) for w in winner_list]}', ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def reroll(ctx, message_id: int, winners: int = 1):
    try:
        msg = await ctx.channel.fetch_message(message_id)
        reaction = discord.utils.get(msg.reactions, emoji='🎉')
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            return await ctx.send('❌ No entries found.')
        winner_list = random.sample(users, min(winners, len(users)))
        winner_mentions = ', '.join(w.mention for w in winner_list)
        await ctx.send(f'🎉 New winner(s): {winner_mentions}!')
    except:
        await ctx.send('❌ Could not find that message.')

# ---------- Tickets ----------
ticket_topics = ['General Support', 'Bug Report', 'Ban Appeal', 'Partnership', 'Purchase Issue', 'Other']

@bot.command()
async def ticket(ctx, *, reason='General Support'):
    guild = ctx.guild
    settings = load_json('settings.json')
    tickets = load_json('tickets.json')
    if 'count' not in tickets:
        tickets['count'] = 0
    tickets['count'] += 1
    ticket_num = tickets['count']

    # Find matching topic for channel name
    topic_slug = reason.lower().replace(' ', '-')[:20]
    channel_name = f'ticket-{ticket_num:04d}-{topic_slug}'

    category_id = settings.get('ticket_category')
    category = guild.get_channel(int(category_id)) if category_id else None

    # Support role
    support_role_id = settings.get('ticket_support_role')
    support_role = guild.get_role(int(support_role_id)) if support_role_id else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category, topic=f'Ticket #{ticket_num:04d} | {ctx.author} | {reason}')

    if 'tickets' not in tickets:
        tickets['tickets'] = []
    tickets['tickets'].insert(0, {
        'id': ticket_num,
        'user': str(ctx.author),
        'user_id': str(ctx.author.id),
        'reason': reason,
        'channel': channel_name,
        'channel_id': str(channel.id),
        'status': 'open',
        'time': datetime.datetime.utcnow().isoformat()
    })
    save_json('tickets.json', tickets)

    # Ticket panel embed (Ticket Tool style)
    embed = discord.Embed(
        title=f'🎫 Ticket #{ticket_num:04d}',
        description=f'**Topic:** {reason}\n**Opened by:** {ctx.author.mention}\n\nSupport will be with you shortly! Please describe your issue in detail.\n\n> Use the buttons below to manage this ticket.',
        color=0x5865F2,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text='KPT_BOT Ticket System')

    view = discord.ui.View()
    close_btn = discord.ui.Button(label='🔒 Close Ticket', style=discord.ButtonStyle.danger, custom_id=f'close_{channel.id}')
    claim_btn = discord.ui.Button(label='✋ Claim', style=discord.ButtonStyle.secondary, custom_id=f'claim_{channel.id}')
    view.add_item(close_btn)
    view.add_item(claim_btn)

    await channel.send(f'{ctx.author.mention}{" " + support_role.mention if support_role else ""}', embed=embed, view=view)

    confirm = discord.Embed(description=f'✅ Your ticket has been created: {channel.mention}', color=0x00FF88)
    await ctx.send(embed=confirm, delete_after=10)
    add_log('TICKET_OPEN', f'{ctx.author} opened ticket #{ticket_num:04d}: {reason}', guild.id)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or 'custom_id' not in interaction.data:
        return
    custom_id = interaction.data['custom_id']

    if custom_id.startswith('close_'):
        if not interaction.user.guild_permissions.manage_channels and str(interaction.user.id) not in interaction.channel.topic:
            await interaction.response.send_message('❌ Only the ticket owner or staff can close this.', ephemeral=True)
            return
        embed = discord.Embed(description='🔒 Ticket closing in 5 seconds...', color=0xFF4466)
        await interaction.response.send_message(embed=embed)
        tickets = load_json('tickets.json')
        for t in tickets.get('tickets', []):
            if t.get('channel_id') == str(interaction.channel.id):
                t['status'] = 'closed'
        save_json('tickets.json', tickets)
        add_log('TICKET_CLOSE', f'{interaction.user} closed ticket {interaction.channel.name}', interaction.guild.id)
        await asyncio.sleep(5)
        await interaction.channel.delete()

    elif custom_id.startswith('claim_'):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message('❌ Only staff can claim tickets.', ephemeral=True)
            return
        embed = discord.Embed(description=f'✋ Ticket claimed by {interaction.user.mention}', color=0x00FF88)
        await interaction.response.send_message(embed=embed)
        add_log('TICKET_CLAIM', f'{interaction.user} claimed {interaction.channel.name}', interaction.guild.id)

@bot.command()
async def closeticket(ctx):
    if 'ticket-' not in ctx.channel.name:
        return await ctx.send('❌ This is not a ticket channel.')
    await ctx.send('🔒 Closing ticket in 5 seconds...')
    tickets = load_json('tickets.json')
    for t in tickets.get('tickets', []):
        if t.get('channel_id') == str(ctx.channel.id):
            t['status'] = 'closed'
    save_json('tickets.json', tickets)
    add_log('TICKET_CLOSE', f'{ctx.author} closed {ctx.channel.name}', ctx.guild.id)
    await asyncio.sleep(5)
    await ctx.channel.delete()

# ---------- Custom Commands ----------
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
        await ctx.send(f'✅ Deleted custom command `{name}`.')
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

# ---------- Settings ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, prefix: str):
    settings = load_json('settings.json')
    settings['prefix'] = prefix
    save_json('settings.json', settings)
    await ctx.send(f'✅ Prefix changed to `{prefix}`')
    add_log('SETTINGS', f'{ctx.author} changed prefix to {prefix}', ctx.guild.id)

# ---------- Run ----------
bot.run(os.getenv('DISCORD_TOKEN'))
