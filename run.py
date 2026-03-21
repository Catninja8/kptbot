import threading
import subprocess
import sys
import os

os.makedirs('data', exist_ok=True)

def run_bot():
    subprocess.run([sys.executable, 'bot.py'])

t = threading.Thread(target=run_bot, daemon=True)
t.start()

subprocess.run([sys.executable, 'dashboard.py'])
