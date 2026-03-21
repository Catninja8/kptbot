from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json, os, datetime, hashlib, secrets

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DATA_DIR = 'data'

def load_json(path):
    full = os.path.join(DATA_DIR, path)
    if not os.path.exists(full): return {}
    with open(full, 'r') as f: return json.load(f)

def save_json(path, data):
    full = os.path.join(DATA_DIR, path)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(full, 'w') as f: json.dump(data, f, indent=2)

def get_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_auth():
    """Check if user is logged in."""
    return session.get('logged_in') == True

def is_admin_user():
    """Check if logged in user has admin privileges."""
    return session.get('is_admin') == True

# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        # Get credentials from environment variables
        valid_user = os.environ.get('DASHBOARD_USER', 'admin')
        valid_pass = os.environ.get('DASHBOARD_PASS', 'kptbot2024')

        if username == valid_user and password == valid_pass:
            session['logged_in'] = True
            session['username'] = username
            session['is_admin'] = True
            session.permanent = True
            if request.is_json:
                return jsonify({'success': True})
            return redirect('/')
        else:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Invalid username or password'})
            return render_template('login.html', error='Invalid username or password')

    if check_auth():
        return redirect('/')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ============================================================
# PROTECTED ROUTES — require login
# ============================================================

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            if request.is_json:
                return jsonify({'error': 'Unauthorized', 'redirect': '/login'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@require_auth
def index():
    return render_template('index.html', username=session.get('username', 'Admin'))

# ============================================================
# API ROUTES — all protected
# ============================================================

@app.route('/api/me')
@require_auth
def get_me():
    return jsonify({'username': session.get('username'), 'is_admin': session.get('is_admin')})

@app.route('/api/server')
@require_auth
def get_server():
    return jsonify(load_json('server_cache.json'))

@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    return jsonify(load_json('settings.json'))

@app.route('/api/settings', methods=['POST'])
@require_auth
def post_settings():
    data = request.json
    settings = load_json('settings.json')
    settings.update(data)
    save_json('settings.json', settings)
    return jsonify({'success': True})

@app.route('/api/stats')
@require_auth
def get_stats():
    logs = load_json('logs.json').get('logs', [])
    warns = load_json('warns.json')
    tickets = load_json('tickets.json')
    custom_cmds = load_json('custom_commands.json')
    gws = load_json('giveaways.json')
    total_warns = sum(len(v) for v in warns.values() if isinstance(v, list))
    ticket_list = tickets.get('tickets', [])
    open_tickets = sum(1 for t in ticket_list if t.get('status') == 'open')
    active_gws = sum(1 for g in gws.get('active', []) if g.get('status') == 'active')
    return jsonify({'total_logs': len(logs), 'total_warns': total_warns, 'open_tickets': open_tickets, 'total_tickets': len(ticket_list), 'custom_commands': len(custom_cmds), 'active_giveaways': active_gws})

@app.route('/api/logs')
@require_auth
def get_logs():
    return jsonify(load_json('logs.json').get('logs', []))

@app.route('/api/warns')
@require_auth
def get_warns():
    return jsonify(load_json('warns.json'))

@app.route('/api/tickets')
@require_auth
def get_tickets():
    return jsonify(load_json('tickets.json').get('tickets', []))

@app.route('/api/giveaways')
@require_auth
def get_giveaways():
    return jsonify(load_json('giveaways.json').get('active', []))

@app.route('/api/giveaways/create', methods=['POST'])
@require_auth
def create_giveaway():
    data = request.json
    pending = load_json('pending_actions.json')
    if 'actions' not in pending: pending['actions'] = []
    pending['actions'].append({'type': 'giveaway', 'data': data, 'time': datetime.datetime.utcnow().isoformat()})
    save_json('pending_actions.json', pending)
    return jsonify({'success': True, 'message': '✅ Giveaway queued! Bot will post it shortly.'})

@app.route('/api/announce', methods=['POST'])
@require_auth
def post_announcement():
    data = request.json
    pending = load_json('pending_actions.json')
    if 'actions' not in pending: pending['actions'] = []
    pending['actions'].append({'type': 'announce', 'data': data, 'time': datetime.datetime.utcnow().isoformat()})
    save_json('pending_actions.json', pending)
    return jsonify({'success': True, 'message': '✅ Announcement queued!'})

@app.route('/api/ticketpanel/post', methods=['POST'])
@require_auth
def post_ticket_panel():
    data = request.json
    pending = load_json('pending_actions.json')
    if 'actions' not in pending: pending['actions'] = []
    pending['actions'].append({'type': 'ticketpanel', 'data': data, 'time': datetime.datetime.utcnow().isoformat()})
    save_json('pending_actions.json', pending)
    return jsonify({'success': True, 'message': '✅ Ticket panel queued!'})

@app.route('/api/commands', methods=['GET'])
@require_auth
def get_commands():
    return jsonify(load_json('custom_commands.json'))

@app.route('/api/commands', methods=['POST'])
@require_auth
def post_command():
    data = request.json
    cmds = load_json('custom_commands.json')
    cmds[data['name'].lower()] = data['response']
    save_json('custom_commands.json', cmds)
    return jsonify({'success': True})

@app.route('/api/commands/<name>', methods=['DELETE'])
@require_auth
def delete_command(name):
    cmds = load_json('custom_commands.json')
    if name in cmds: del cmds[name]
    save_json('custom_commands.json', cmds)
    return jsonify({'success': True})

@app.route('/api/panel', methods=['GET'])
@require_auth
def get_panel():
    cfg = load_json('panel_config.json')
    return jsonify(cfg if cfg else {})

@app.route('/api/panel', methods=['POST'])
@require_auth
def save_panel():
    save_json('panel_config.json', request.json)
    return jsonify({'success': True})

@app.route('/api/panel/reset', methods=['POST'])
@require_auth
def reset_panel():
    save_json('panel_config.json', {})
    return jsonify({'success': True})

@app.route('/api/messages', methods=['GET'])
@require_auth
def get_messages():
    cfg = load_json('messages_config.json')
    return jsonify(cfg if cfg else {})

@app.route('/api/messages', methods=['POST'])
@require_auth
def save_messages():
    save_json('messages_config.json', request.json)
    return jsonify({'success': True})

@app.route('/api/messages/reset', methods=['POST'])
@require_auth
def reset_messages():
    save_json('messages_config.json', {})
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
