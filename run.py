import threading
import subprocess
import sys
import os
import time  # Added for the delay

os.makedirs('data', exist_ok=True)

def run_bot():
    print("🤖 Starting KPT_BOT...")
    while True:
        # This starts bot.py and waits for it to finish/crash
        process = subprocess.run([sys.executable, 'bot.py'])
        
        # If bot.py crashes or is rate-limited, wait 60 seconds before trying again
        # This prevents the "ban loop" on Render/Cloudflare
        print("⚠️ Bot stopped or was rate limited. Retrying in 60 seconds...")
        time.sleep(60)

# Start bot in background thread
t = threading.Thread(target=run_bot, daemon=True)
t.start()

# Run dashboard in main thread (keeps container alive)
print("🌐 Starting dashboard...")
subprocess.run([sys.executable, 'dashboard.py'])
