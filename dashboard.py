from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)
DATA_DIR = 'data'

def load_json(path):
    full = os.path.join(DATA_DIR, path)
    if not os.path.exists(full):
        return {}
    with open(full, 'r') as f:
        return json.load(f)

def save_json(path, data):
    full = os.path.join(DATA_DIR, path)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(full, 'w') as f:
        json.dump(data, f, indent=2)

DEFAULT_PANEL_CONFIG = {
    'panel_title': '🎫 KaramPlaysThis Support',
    'panel_description': '**Need help? Open a ticket below!**\n\n🙋 **General Support** — General questions or server help\n🔴 **Stream Problem** — Issues with KaramPlaysThis streams\n🚨 **Report a Player** — Report someone breaking the rules\n🤝 **Partnership** — Collab or partnership requests\n❓ **Other** — Anything else\n\n> Select a category from the dropdown below to get started.',
    'panel_footer': 'KPT_BOT Ticket System • One ticket per issue please!',
    'panel_color': '5865F2',
    'dropdown_placeholder': '📂 Select a ticket category...',
    'categories': [
        {
            'id': 'general','label': '🙋 General Support','description': 'General questions or server help',
            'slug': 'general','color': '5865F2','modal_title': '🙋 General Support',
            'fields': [
                {'label': 'What do you need help with?','placeholder': 'Brief summary of your issue...','style': 'short','required': True,'max_length': 100},
                {'label': 'Please describe in detail','placeholder': 'Give us as much info as possible...','style': 'long','required': True,'max_length': 1000},
                {'label': 'What have you already tried?','placeholder': 'e.g. Checked FAQ, asked in chat...','style': 'short','required': False,'max_length': 200}
            ]
        },
        {
            'id': 'stream','label': '🔴 Stream Problem','description': 'Issues watching KaramPlaysThis streams',
            'slug': 'stream','color': 'FF4466','modal_title': '🔴 Stream Problem',
            'fields': [
                {'label': 'What is the stream problem?','placeholder': 'e.g. Cannot watch stream, buffering...','style': 'short','required': True,'max_length': 100},
                {'label': 'Which platform?','placeholder': 'e.g. Twitch, YouTube...','style': 'short','required': True,'max_length': 50},
                {'label': 'What device are you using?','placeholder': 'e.g. PC, Phone, Xbox...','style': 'short','required': True,'max_length': 50},
                {'label': 'Any extra details?','placeholder': 'Error messages, when it started...','style': 'long','required': False,'max_length': 500}
            ]
        },
        {
            'id': 'report','label': '🚨 Report a Player','description': 'Report a member for rule breaking',
            'slug': 'report','color': 'FF9900','modal_title': '🚨 Report a Player',
            'fields': [
                {'label': 'Username of the player','placeholder': 'e.g. BadUser#1234','style': 'short','required': True,'max_length': 100},
                {'label': 'Reason for report','placeholder': 'e.g. Harassment, cheating...','style': 'short','required': True,'max_length': 100},
                {'label': 'What happened? (full details)','placeholder': 'Describe the full situation...','style': 'long','required': True,'max_length': 1000},
                {'label': 'Do you have evidence?','placeholder': 'Yes / No — attach screenshots in ticket','style': 'short','required': False,'max_length': 200}
            ]
        },
        {
            'id': 'partner','label': '🤝 Partnership','description': 'Partnership or collab requests',
            'slug': 'partner','color': '00d4ff','modal_title': '🤝 Partnership Request',
            'fields': [
                {'label': 'Your name / brand name','placeholder': 'e.g. YourBrand','style': 'short','required': True,'max_length': 100},
                {'label': 'Platform & follower count','placeholder': 'e.g. YouTube — 5,000 subs','style': 'short','required': True,'max_length': 100},
                {'label': 'What are you proposing?','placeholder': 'Describe your partnership idea...','style': 'long','required': True,'max_length': 1000},
                {'label': 'Your social links','placeholder': 'e.g. youtube.com/yourchannel','style': 'short','required': True,'max_length': 200}
            ]
        },
        {
            'id': 'other','label': '❓ Other','description': 'Anything else not listed above',
            'slug': 'other','color': '8892b0','modal_title': '❓ Other',
            'fields': [
                {'label': 'Subject','placeholder': 'Brief subject of your ticket...','style': 'short','required': True,'max_length': 100},
                {'label': 'Full details','placeholder': 'Explain your situation in full detail...','style': 'long','required': True,'max_length': 1000}
            ]
        }
    ]
}

def get_panel_config():
    cfg = load_json('panel_config.json')
    if not cfg:
        save_json('panel_config.json', DEFAULT_PANEL_CONFIG)
        return DEFAULT_PANEL_CONFIG
    return cfg

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(load_json('settings.json'))

@app.route('/api/settings', methods=['POST'])
def post_settings():
    data = request.json
    settings = load_json('settings.json')
    settings.update(data)
    save_json('settings.json', settings)
    return jsonify({'success': True})

@app.route('/api/stats')
def get_stats():
    logs = load_json('logs.json').get('logs', [])
    warns = load_json('warns.json')
    tickets = load_json('tickets.json')
    custom_cmds = load_json('custom_commands.json')
    total_warns = sum(len(v) for v in warns.values() if isinstance(v, list))
    ticket_list = tickets.get('tickets', [])
    open_tickets = sum(1 for t in ticket_list if t.get('status') == 'open')
    return jsonify({'total_logs': len(logs),'total_warns': total_warns,'open_tickets': open_tickets,'total_tickets': len(ticket_list),'custom_commands': len(custom_cmds)})

@app.route('/api/logs')
def get_logs():
    return jsonify(load_json('logs.json').get('logs', []))

@app.route('/api/warns')
def get_warns():
    return jsonify(load_json('warns.json'))

@app.route('/api/tickets')
def get_tickets():
    return jsonify(load_json('tickets.json').get('tickets', []))

@app.route('/api/commands', methods=['GET'])
def get_commands():
    return jsonify(load_json('custom_commands.json'))

@app.route('/api/commands', methods=['POST'])
def post_command():
    data = request.json
    cmds = load_json('custom_commands.json')
    cmds[data['name'].lower()] = data['response']
    save_json('custom_commands.json', cmds)
    return jsonify({'success': True})

@app.route('/api/commands/<name>', methods=['DELETE'])
def delete_command(name):
    cmds = load_json('custom_commands.json')
    if name in cmds:
        del cmds[name]
        save_json('custom_commands.json', cmds)
    return jsonify({'success': True})

@app.route('/api/panel', methods=['GET'])
def get_panel():
    return jsonify(get_panel_config())

@app.route('/api/panel', methods=['POST'])
def save_panel():
    save_json('panel_config.json', request.json)
    return jsonify({'success': True})

@app.route('/api/panel/reset', methods=['POST'])
def reset_panel():
    save_json('panel_config.json', DEFAULT_PANEL_CONFIG)
    return jsonify({'success': True})


# --- Messages Config ---
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

@app.route('/api/messages', methods=['GET'])
def get_messages():
    cfg = load_json('messages_config.json')
    return jsonify(cfg if cfg else DEFAULT_MSGS)

@app.route('/api/messages', methods=['POST'])
def save_messages():
    save_json('messages_config.json', request.json)
    return jsonify({'success': True})

@app.route('/api/messages/reset', methods=['POST'])
def reset_messages():
    save_json('messages_config.json', DEFAULT_MSGS)
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
