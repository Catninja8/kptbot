from flask import Flask, render_template, request, jsonify
import json, os, datetime

app = Flask(__name__)
DATA_DIR = 'data'

def load_json(path):
    full = os.path.join(DATA_DIR, path)
    if not os.path.exists(full): return {}
    with open(full, 'r') as f: return json.load(f)

def save_json(path, data):
    full = os.path.join(DATA_DIR, path)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(full, 'w') as f: json.dump(data, f, indent=2)

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

DEFAULT_PANEL = {
    'panel_title':'🎫 KaramPlaysThis Support','panel_description':'**Need help? Open a ticket below!**\n\nSelect a category from the dropdown to get started.','panel_footer':'KPT_BOT Ticket System • One ticket per issue please!','panel_color':'5865F2','dropdown_placeholder':'📂 Select a ticket category...',
    'categories':[
        {'id':'general','label':'🙋 General Support','description':'General questions or server help','slug':'general','color':'5865F2','modal_title':'🙋 General Support','fields':[{'label':'What do you need help with?','placeholder':'Brief summary...','style':'short','required':True,'max_length':100},{'label':'Please describe in detail','placeholder':'Full details...','style':'long','required':True,'max_length':1000},{'label':'What have you already tried?','placeholder':'e.g. Checked FAQ...','style':'short','required':False,'max_length':200}]},
        {'id':'other','label':'❓ Other','description':'Anything else','slug':'other','color':'8892b0','modal_title':'❓ Other','fields':[{'label':'Subject','placeholder':'Brief subject...','style':'short','required':True,'max_length':100},{'label':'Full details','placeholder':'Full details...','style':'long','required':True,'max_length':1000}]}
    ]
}

@app.route('/')
def index(): return render_template('index.html')

# --- Server Cache (from bot) ---
@app.route('/api/server')
def get_server(): return jsonify(load_json('server_cache.json'))

# --- Settings ---
@app.route('/api/settings', methods=['GET'])
def get_settings(): return jsonify(load_json('settings.json'))

@app.route('/api/settings', methods=['POST'])
def post_settings():
    data = request.json; settings = load_json('settings.json'); settings.update(data)
    save_json('settings.json', settings); return jsonify({'success': True})

# --- Stats ---
@app.route('/api/stats')
def get_stats():
    logs = load_json('logs.json').get('logs', [])
    warns = load_json('warns.json')
    tickets = load_json('tickets.json')
    custom_cmds = load_json('custom_commands.json')
    giveaways = load_json('giveaways.json')
    total_warns = sum(len(v) for v in warns.values() if isinstance(v, list))
    ticket_list = tickets.get('tickets', [])
    open_tickets = sum(1 for t in ticket_list if t.get('status') == 'open')
    active_gws = sum(1 for g in giveaways.get('active',[]) if g.get('status')=='active')
    return jsonify({'total_logs':len(logs),'total_warns':total_warns,'open_tickets':open_tickets,'total_tickets':len(ticket_list),'custom_commands':len(custom_cmds),'active_giveaways':active_gws})

# --- Logs ---
@app.route('/api/logs')
def get_logs(): return jsonify(load_json('logs.json').get('logs', []))

# --- Warns ---
@app.route('/api/warns')
def get_warns(): return jsonify(load_json('warns.json'))

@app.route('/api/warns/<uid>', methods=['DELETE'])
def clear_warns(uid):
    warns = load_json('warns.json'); warns[uid] = []
    save_json('warns.json', warns); return jsonify({'success': True})

# --- Tickets ---
@app.route('/api/tickets')
def get_tickets(): return jsonify(load_json('tickets.json').get('tickets', []))

# --- Giveaways ---
@app.route('/api/giveaways')
def get_giveaways(): return jsonify(load_json('giveaways.json').get('active', []))

@app.route('/api/giveaways', methods=['POST'])
def create_giveaway():
    data = request.json
    gws = load_json('giveaways.json')
    if 'active' not in gws: gws['active'] = []
    gw = {'message_id': None, 'channel_id': data.get('channel_id'), 'prize': data.get('prize'), 'winners': data.get('winners', 1), 'end_time': data.get('end_time'), 'host': 'Dashboard', 'status': 'pending', 'created': datetime.datetime.utcnow().isoformat()}
    gws['active'].append(gw)
    # Write a pending action for bot to pick up
    actions = load_json('pending_actions.json')
    if 'actions' not in actions: actions['actions'] = []
    actions['actions'].append({'type': 'giveaway', 'data': data, 'time': datetime.datetime.utcnow().isoformat()})
    save_json('pending_actions.json', actions)
    save_json('giveaways.json', gws)
    return jsonify({'success': True})

# --- Announcements ---
@app.route('/api/announce', methods=['POST'])
def post_announce():
    data = request.json
    actions = load_json('pending_actions.json')
    if 'actions' not in actions: actions['actions'] = []
    actions['actions'].append({'type': 'announce', 'data': data, 'time': datetime.datetime.utcnow().isoformat()})
    save_json('pending_actions.json', actions)
    return jsonify({'success': True})

# --- Ticket Panel post action ---
@app.route('/api/ticketpanel', methods=['POST'])
def post_ticketpanel():
    data = request.json
    actions = load_json('pending_actions.json')
    if 'actions' not in actions: actions['actions'] = []
    actions['actions'].append({'type': 'ticketpanel', 'data': data, 'time': datetime.datetime.utcnow().isoformat()})
    save_json('pending_actions.json', actions)
    return jsonify({'success': True})

# --- Custom Commands ---
@app.route('/api/commands', methods=['GET'])
def get_commands(): return jsonify(load_json('custom_commands.json'))

@app.route('/api/commands', methods=['POST'])
def post_command():
    data = request.json; cmds = load_json('custom_commands.json')
    cmds[data['name'].lower()] = data['response']; save_json('custom_commands.json', cmds)
    return jsonify({'success': True})

@app.route('/api/commands/<name>', methods=['DELETE'])
def delete_command(name):
    cmds = load_json('custom_commands.json')
    if name in cmds: del cmds[name]; save_json('custom_commands.json', cmds)
    return jsonify({'success': True})

# --- Panel Config ---
@app.route('/api/panel', methods=['GET'])
def get_panel():
    cfg = load_json('panel_config.json'); return jsonify(cfg if cfg else DEFAULT_PANEL)

@app.route('/api/panel', methods=['POST'])
def save_panel(): save_json('panel_config.json', request.json); return jsonify({'success': True})

@app.route('/api/panel/reset', methods=['POST'])
def reset_panel(): save_json('panel_config.json', DEFAULT_PANEL); return jsonify({'success': True})

# --- Messages Config ---
@app.route('/api/messages', methods=['GET'])
def get_messages():
    cfg = load_json('messages_config.json'); return jsonify(cfg if cfg else DEFAULT_MSGS)

@app.route('/api/messages', methods=['POST'])
def save_messages(): save_json('messages_config.json', request.json); return jsonify({'success': True})

@app.route('/api/messages/reset', methods=['POST'])
def reset_messages(): save_json('messages_config.json', DEFAULT_MSGS); return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
