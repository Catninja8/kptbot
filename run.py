import threading
import subprocess
import sys
import os

os.makedirs('data', exist_ok=True)

def run_bot():
    subprocess.run([sys.executable, 'bot.py'])

def run_dash():
    subprocess.run([sys.executable, 'dashboard.py'])

# Start bot in background thread
t1 = threading.Thread(target=run_bot, daemon=True)
t1.start()

# Run dashboard in main thread (keeps container alive)
run_dash()
