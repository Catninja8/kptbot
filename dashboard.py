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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(load_json('settings.json'))

@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.json
    settings = load_json('settings.json')
    settings.update(data)
    save_json('settings.json', settings)
    return jsonify({'success': True})

@app.route('/api/logs')
def get_logs():
    return jsonify(load_json('logs.json').get('logs', []))

@app.route('/api/warns')
def get_warns():
    return jsonify(load_json('warns.json'))

@app.route('/api/tickets')
def get_tickets():
    return jsonify(load_json('tickets.json').get('tickets', []))

@app.route('/api/stats')
def get_stats():
    logs = load_json('logs.json').get('logs', [])
    warns = load_json('warns.json')
    tickets = load_json('tickets.json').get('tickets', [])
    total_warns = sum(len(v) for v in warns.values())
    open_tickets = sum(1 for t in tickets if t.get('status') == 'open')
    return jsonify({
        'total_logs': len(logs),
        'total_warns': total_warns,
        'open_tickets': open_tickets,
        'total_tickets': len(tickets)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
