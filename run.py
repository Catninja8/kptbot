import threading
import subprocess
import sys
import os

os.makedirs('data', exist_ok=True)

def run_bot():
    print("Starting KPT_BOT...")
    subprocess.run([sys.executable, 'bot.py'])

t = threading.Thread(target=run_bot, daemon=True)
t.start()

print("Starting dashboard...")
subprocess.run([sys.executable, 'dashboard.py'])
```

---

After committing Railway will redeploy and you should see:
```
Starting KPT_BOT...
Starting dashboard...
✅ Logged in as KPT_BOT
