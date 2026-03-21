import threading
import subprocess
import sys
import os

os.makedirs('data', exist_ok=True)

def run_bot():
    subprocess.run([sys.executable, 'bot.py'])

def run_dash():
    subprocess.run([sys.executable, 'dashboard.py'])

t1 = threading.Thread(target=run_bot, daemon=True)
t2 = threading.Thread(target=run_dash, daemon=True)
t1.start()
t2.start()
t1.join()
t2.join()
