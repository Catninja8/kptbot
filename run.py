import threading
import subprocess
import sys
import os

os.makedirs('data', exist_ok=True)

def run_bot():
    print("🤖 Starting KPT_BOT...")
    subprocess.run([sys.executable, 'bot.py'])

# Start bot in background thread
t = threading.Thread(target=run_bot, daemon=True)
t.start()

# Run dashboard in main thread (keeps container alive)
print("🌐 Starting dashboard...")
subprocess.run([sys.executable, 'dashboard.py'])
