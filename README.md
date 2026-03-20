# KPT_BOT - Setup Guide

## 📁 File Structure
```
kptbot/
├── bot.py          ← Discord bot
├── dashboard.py    ← Web dashboard server
├── .env            ← Your secret token (never share this!)
├── requirements.txt
├── templates/
│   └── index.html  ← Dashboard UI
└── data/           ← Auto-created by bot
    ├── settings.json
    ├── logs.json
    ├── warns.json
    └── tickets.json
```

---

## ⚡ Setup Steps

### 1. Reset your token (IMPORTANT!)
Your old token was exposed. Go to:
https://discord.com/developers/applications → Your App → Bot → Reset Token
Copy the new token.

### 2. Paste token into .env
Open `.env` and replace `paste_your_new_token_here` with your real token.

### 3. Install dependencies
Open Command Prompt in the kptbot folder and run:
```
pip install -r requirements.txt
```

### 4. Enable Intents in Developer Portal
Go to: discord.com/developers/applications → Your App → Bot
Enable ALL of these:
✅ Server Members Intent
✅ Message Content Intent

### 5. Run the bot
```
python bot.py
```

### 6. Run the dashboard (in a SEPARATE Command Prompt window)
```
python dashboard.py
```
Then open: http://localhost:5000

---

## 🤖 Bot Commands

| Command | Description | Permission |
|---------|-------------|------------|
| !ping | Check latency | Everyone |
| !info | Bot stats | Everyone |
| !kick @user [reason] | Kick member | Kick Members |
| !ban @user [reason] | Ban member | Ban Members |
| !mute @user [minutes] | Timeout member | Moderate Members |
| !unmute @user | Remove timeout | Moderate Members |
| !warn @user [reason] | Warn member | Kick Members |
| !warnings @user | See warnings | Everyone |
| !clearwarns @user | Clear warnings | Admin |
| !purge [amount] | Delete messages | Manage Messages |
| !setprefix [prefix] | Change prefix | Admin |
| !automod on/off | Toggle word filter | Admin |
| !addbadword [word] | Add banned word | Admin |
| !ticket [reason] | Open support ticket | Everyone |
| !closeticket | Close ticket channel | In ticket only |

---

## 🌐 Dashboard Features
- 📊 Overview with live stats
- 📋 Activity logs (all mod actions)
- ⚙️ Settings (prefix, auto-mod toggle)
- 🚫 Bad words filter management
- ⚠️ View all user warnings
- 🎫 Ticket history
- 💬 Command reference
