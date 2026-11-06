import threading, asyncio, re, sqlite3, secrets, string, os, time
from datetime import datetime
from flask import Flask, request, render_template_string, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import telebot
    from telebot import types
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
except ImportError:
    pass

# ================= CONFIG =================
API_ID = 37325833
API_HASH = '8d82b6543b9631209aebf4b5e03409fc'
# Naya Session String yahan add kar diya hai
SESSION_STR = '1BVtsOHUBu8J5LUCLkS6vRb7Sn86yjfPWuaWejjvfWClLLgvvdptBpa0lNXwg0RPO5yn5Wh61VgXy_UBEWX5jeXcWOnEu2CqXCkvjierGj730SpMwoSCzGi35phwBAayzzvXNcL-OXoDugc28Wfop-FkgTaHItalB4gObWpbST748Il6GJ4YXKKa8Gsrw9uavs_tJB8rCqOr31B0JdOBMn5szfBBnx2dLF6fArrZ3CSv1QSmE2UkhDm--qFPP4uc5Ytet5HT-k7BW5JDzHC7xcRVtweNr_T45-gVASzzXXxzaBnJCIeN7AWPn-KuQJvn3W8niq54TZf4fCWYD8-u9PDF9d1VNraI='
TARGET_BOT = '@Osint2_info_bot'
BOT_TOKEN = '9249884434:AAFIQieRI5vaydKvHRI6IC2PTeMpOm0q4pA'
WEB_USER = "RICH"
WEB_PASS = "DK124421"
SEARCH_COST = 100
SIGNUP_BONUS = 50
REFERRAL_BONUS = 100
DB = "osint.db"
TG_HELP_ID = "https://t.me/MrRichYT"

if not os.path.exists('static'):
    os.makedirs('static')
LOGO_FILE = os.path.join('static', 'custom_logo.jpg')
BG_FILE = os.path.join('static', 'custom_bg.bin')
BG_EXT_FILE = os.path.join('static', 'bg_ext.txt')

# ================= DATABASE =================
def init_db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,username TEXT UNIQUE,mobile TEXT,password_hash TEXT,raw_password TEXT,referral_code TEXT UNIQUE,referred_by TEXT,wallet REAL DEFAULT 0,is_admin INTEGER DEFAULT 0,is_blocked INTEGER DEFAULT 0,created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS redeem_codes(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE,amount REAL,created_by TEXT,used_by TEXT,status TEXT DEFAULT 'active',created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT UNIQUE, value TEXT)")
    
    if not c.execute("SELECT 1 FROM users WHERE username=?", (WEB_USER,)).fetchone():
        c.execute("INSERT INTO users(name,username,mobile,password_hash,raw_password,referral_code,wallet,is_admin,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  ("Admin", WEB_USER, "0000000000", generate_password_hash(WEB_PASS), WEB_PASS, "RICH-ADMIN1", 999999999, 1, datetime.now().isoformat()))
    else:
        # Force update password
        c.execute("UPDATE users SET password_hash=?, raw_password=? WHERE username=?", 
                  (generate_password_hash(WEB_PASS), WEB_PASS, WEB_USER))
    
    if not c.execute("SELECT 1 FROM settings WHERE key='panel_name'").fetchone():
        c.execute("INSERT INTO settings(key, value) VALUES('panel_name', 'RICH')")
    c.commit(); c.close()

def get_setting(key):
    c = sqlite3.connect(DB)
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    c.close()
    return row[0] if row else ""

def set_setting(key, val):
    c = sqlite3.connect(DB)
    c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, val))
    c.commit(); c.close()

def gen_ref():
    while True:
        code = "RICH-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        c = sqlite3.connect(DB)
        if not c.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            c.close(); return code
        c.close()

def get_user(u):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
    c.close(); return dict(r) if r else None

def update_wallet(u, amt):
    c = sqlite3.connect(DB)
    row = c.execute("SELECT is_admin,wallet FROM users WHERE username=?", (u,)).fetchone()
    if not row: c.close(); return False
    if row[0] == 1: c.close(); return True
    if row[1] + amt < 0: c.close(); return False
    c.execute("UPDATE users SET wallet=wallet+? WHERE username=?", (amt, u))
    c.commit(); c.close(); return True

init_db()

# ================= BOT SETUP =================
try:
    bot = telebot.TeleBot(BOT_TOKEN, num_threads=2, threaded=False)
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH, loop=loop)
    lock = threading.Lock()
    captured = None
    ev = None
    last_result_id = None

    MENU = [
        ("🔍 Num Lookup", "🔍 Num Lookup", "10 Digit Mobile..."),
        ("🧠 TG ID ➔ Num", "🧠 TG ID ➔ Num", "Telegram ID..."),
        ("👤 TG User ➔ Num", "👤 TG User ➔ Num", "Username @..."),
        ("📁 Num ➔ All Info", "📁 Num ➔ All Info", "10 Digit Mobile..."),
        ("🪪 Aadhaar Info", "🪪 Aadhaar Info", "12 Digit Aadhaar..."),
        ("👨‍👩‍👧‍👦 Aadhaar Family", "👨‍👩‍👧‍👦 Aadhaar Family", "Aadhaar Number..."),
        ("🆔 Aadhaar ➔ PAN", "🆔 Aadhaar ➔ PAN", "Aadhaar Number..."),
        ("✉️ Email ➔ Num", "✉️ Email ➔ Num", "Email..."),
        ("🌐 Web Scraper", "🌐 Web Scraper", "URL..."),
        ("🚗 Vehicle ➔ Num", "🚗 Vehicle ➔ Num", "Vehicle Number..."),
        ("🏡 Vehicle Address", "🏡 Vehicle Address", "Vehicle Number..."),
        ("📄 RC ➔ PDF", "📄 RC ➔ PDF", "Vehicle Number..."),
        ("📝 Name Info", "📝 Name Info", "Full Name..."),
        ("🆔 Aadhaar ➔ Ration", "🆔 Aadhaar ➔ Ration", "Aadhaar Number..."),
        ("💳 PAN Info", "💳 PAN Info", "PAN Number..."),
        ("💼 PAN ➔ GST", "💼 PAN ➔ GST", "PAN Number..."),
    ]

    def main_menu():
        m = types.InlineKeyboardMarkup(row_width=2)
        m.add(*[types.InlineKeyboardButton(text=d, callback_data="cmd|"+a) for d, a, p in MENU])
        return m

    def extract_text(msg):
        if not msg: return ""
        return msg.raw_text or msg.text or ""

    def wm(text):
        if not text: return ""
        lines = text.split('\n')
        clean_lines = []
        for ln in lines:
            s = ln.strip()
            if not s: continue
            if "@suryaxz" in s or "COPY CODE" in s or "By :" in s: continue
            clean_lines.append(ln)

        html_lines = []
        for ln in clean_lines:
            s = ln.strip()
            if ":" in s and not s.startswith("╔") and not s.startswith("╠") and not s.startswith("╚"):
                parts = s.split(":", 1)
                k = parts[0].strip("║ ").strip()
                v = parts[1].strip("║ ").strip()
                if k and v:
                    html_lines.append(f"<div style='display:flex; margin-bottom:4px;'><span style='color:#ff3333; font-weight:bold; min-width:140px;'>{k}</span> <span style='color:#00ff66;'>: {v}</span></div>")
                else:
                    html_lines.append(f"<div style='color:#00ff66;'>{s}</div>")
            else:
                html_lines.append(f"<div style='color:#00ff66; font-weight:bold;'>{s}</div>")
        return "".join(html_lines)

    def setup_handlers():
        global ev, captured
        if ev is None: ev = asyncio.Event()
        
        @client.on(events.NewMessage(incoming=True))
        async def h(e):
            global captured, ev, last_result_id
            if e.sender_id == (await client.get_entity(TARGET_BOT)).id:
                t = extract_text(e.message).lower()
                if "fetching" in t or "wait" in t: return
                if len(t) > 30 and ("number" in t or "record" in t or "name" in t or "address" in t):
                    if e.message.id != last_result_id:
                        last_result_id = e.message.id
                        captured = e.message
                        ev.set()

    def start_userbot():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.connect())
            setup_handlers()
            print("☠️ Userbot Active")
            loop.run_forever()
        except Exception as ex:
            print("❌ Userbot Error: " + str(ex))

    threading.Thread(target=start_userbot, daemon=True).start()

    async def send_wait(cmd, query):
        global captured, ev
        ev.clear(); captured = None
        await client.send_message(TARGET_BOT, cmd)
        await asyncio.sleep(1.5)
        await client.send_message(TARGET_BOT, query)
        try:
            await asyncio.wait_for(ev.wait(), timeout=30.0)
            await asyncio.sleep(1.0)
            return captured
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            return None

    @bot.message_handler(commands=['start'])
    def start(m):
        bot.send_message(m.chat.id, "⚡ RICH OSINT ⚡\nMenu:", reply_markup=main_menu())

    @bot.callback_query_handler(func=lambda c: True)
    def cb(call):
        if call.data.startswith("cmd|"):
            a = call.data.split("|")[1]
            bot.answer_callback_query(call.id, a)
            msg = bot.send_message(call.message.chat.id, "📡 " + a + "...")
            with lock:
                r = asyncio.run_coroutine_threadsafe(send_wait(a, a), loop).result()
                try: bot.delete_message(call.message.chat.id, msg.message_id)
                except: pass
                if r and extract_text(r):
                    bot.send_message(call.message.chat.id, f"<pre>{extract_text(r)}</pre>", parse_mode='HTML')
                else:
                    bot.send_message(call.message.chat.id, "❌ Timeout or No Text Result", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: True)
    def txt(m):
        msg = bot.send_message(m.chat.id, "📡 Search: " + m.text)
        with lock:
            r = asyncio.run_coroutine_threadsafe(send_wait("🔍 Num Lookup", m.text), loop).result()
            try: bot.delete_message(m.chat.id, msg.message_id)
            except: pass
            if r and extract_text(r):
                bot.send_message(m.chat.id, f"<pre>{extract_text(r)}</pre>", parse_mode='HTML')
            else:
                bot.send_message(m.chat.id, "❌ Timeout or No Text Result", reply_markup=main_menu())

    def run_bot():
        try:
            bot.remove_webhook() # Fix 409 Conflict
            time.sleep(2)
            print("🤖 Telegram Bot Started...")
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print("Bot Error:", e)

except Exception as e:
    print("⚠️ Bot libraries error: " + str(e))
    def run_bot(): pass
    def send_wait(cmd, query): return None
    def extract_text(msg): return ""
    MENU = [("🔍 Num Lookup", "🔍 Num Lookup", "10 Digit Mobile...")]

# ================= FLASK WEB =================
app = Flask(__name__)
app.secret_key = "rich_secret_123_change_me"

def get_bg_html():
    if os.path.exists(BG_FILE) and os.path.exists(BG_EXT_FILE):
        with open(BG_EXT_FILE, 'r') as f:
            ext = f.read().strip()
        if ext in ['mp4', 'webm']:
            return f"<video autoplay loop muted playsinline style='position:fixed; top:0; left:0; width:100%; height:100%; object-fit:cover; z-index:-2;'><source src='/static/custom_bg.bin?t={datetime.now().timestamp()}' type='video/{ext}'></video>"
        else:
            return f"<div style='position:fixed; top:0; left:0; width:100%; height:100%; background:url(\"/static/custom_bg.bin?t={datetime.now().timestamp()}\") center/cover; z-index:-2;'></div>"
    return "<div style='position:fixed; top:0; left:0; width:100%; height:100%; background: radial-gradient(circle at top, #2b0505 0%, #050505 100%); z-index:-2;'></div>"

LOGIN = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{panel_name}} Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}
body{color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}
body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}
.box{background: rgba(15,15,15,0.95);padding:35px 25px;border-radius:16px;max-width:380px;width:100%;border:1px solid #ff3333;text-align:center;box-shadow: 0 0 20px rgba(255, 51, 51, 0.2);position:relative;}
.tg-help{position:absolute;top:15px;right:15px;width:35px;height:35px;border-radius:50%;background:#229ED9;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(34,158,217,0.5);transition:0.2s;border:2px solid #fff;}
.tg-help:hover{transform:scale(1.1);}
.tg-help svg{width:20px;height:20px;fill:#fff;}
.logo{width:130px;height:130px;border-radius:50%;border:2px solid #ff3333;margin:0 auto 20px auto;display:flex;align-items:center;justify-content:center;background: radial-gradient(circle, #ff0000 0%, #000 70%);box-shadow: 0 0 25px #ff0000;position:relative;flex-direction:column;overflow:hidden;}
.logo img{width:100%;height:100%;object-fit:cover;}
.logo .crown{font-size:30px;position:absolute;top:-10px;z-index:2;}
.logo .letter{font-size:50px;font-weight:900;color:#fff;text-shadow:0 0 10px #ff0000;font-family: 'Times New Roman', serif;z-index:1;}
.logo-text{position:absolute;bottom:12px;font-size:9px;letter-spacing:2px;color:#fff;font-weight:bold;border-top:1px solid #ff3333;padding-top:2px;width:60%;z-index:2;}
h2{color:#fff;margin-bottom:5px;font-weight:bold;letter-spacing:1px;font-size:18px;}
h2 span{color:#ff6600;}
p.subtitle{font-size:11px;color:#888;margin-bottom:20px;letter-spacing:1px;}
.input-group{text-align:left;margin-bottom:12px;}
.input-group label{font-size:11px;color:#ccc;margin-bottom:5px;display:block;letter-spacing:1px;}
.input-group input{width:100%;padding:12px;background:#111;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px;}
.input-group input:focus{border-color:#ff3333;outline:none;}
button{width:100%;padding:14px;background: linear-gradient(90deg, #ff3333, #ff6600);color:#fff;font-weight:900;border:none;border-radius:8px;cursor:pointer;font-size:15px;letter-spacing:1px;margin-top:10px;box-shadow: 0 0 15px rgba(255,102,0,0.4);transition:0.3s;}
button:hover{transform:scale(1.02);}
.error{color:#f33;font-size:13px;margin-bottom:10px;background:rgba(255,0,0,0.1);padding:8px;border-radius:5px;}
.link{margin-top:20px;font-size:12px;color:#888;display:flex;justify-content:space-between;}
.link a{color:#ff6600;text-decoration:none;font-weight:bold;}
.checkbox-row{display:flex;align-items:center;justify-content:flex-start;margin-bottom:15px;font-size:12px;color:#aaa;}
.checkbox-row input{width:auto;margin:0 10px 0 0;}
</style></head><body>
""" + get_bg_html() + """
<div class="box">
    <a href="{{tg_link}}" target="_blank" class="tg-help">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.96 1.25-5.54 3.69-.52.36-1 .53-1.42.52-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.36-.48.99-.74 3.86-1.68 6.44-2.79 7.73-3.32 3.68-1.53 4.44-1.8 4.94-1.8.11 0 .35.03.51.15.13.09.2.23.22.37.01.1.01.2-.01.27z"/></svg>
    </a>
    <div class="logo">
        {% if has_logo %}<img src="/static/custom_logo.jpg?t={{time}}" alt="Logo">
        {% else %}<span class="crown">👑</span><span class="letter">R</span><span class="logo-text">VIP PANEL</span>{% endif %}
    </div>
    <h2>Welcome to <span>{{panel_name}}</span></h2>
    <p class="subtitle">⚡ PREMIUM OSINT PANEL ⚡</p>
    {% if error %}<div class="error">{{error}}</div>{% endif %}
    {% if msg %}<div class="error" style="color:#00e676;background:rgba(0,230,118,0.1);">{{msg}}</div>{% endif %}
    <form method="POST">
        <div class="input-group"><label>USERNAME</label><input type="text" name="username" placeholder="Enter username" required></div>
        <div class="input-group"><label>PASSWORD</label><input type="password" name="password" placeholder="Enter password" required></div>
        <div class="checkbox-row"><input type="checkbox" id="rem"><label for="rem">Remember me (stay logged in 24h)</label></div>
        <button type="submit">⚡ ENTER THE {{panel_name|upper}} ⚡</button>
    </form>
    <div class="link"><a href="/forgot">Forgot password?</a> <a href="/signup">Create Account</a></div>
</div></body></html>"""

SIGNUP = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Signup</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}
body{color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}
body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}
.box{background: rgba(15,15,15,0.95);padding:30px 25px;border-radius:16px;max-width:400px;width:100%;border:1px solid #ff3333;}
h2{color:#fff;margin-bottom:20px;text-align:center;letter-spacing:2px;} h2 span{color:#ff6600;}
.input-group{text-align:left;margin-bottom:10px;} .input-group label{font-size:11px;color:#ccc;display:block;margin-bottom:3px;}
.input-group input{width:100%;padding:12px;background:#111;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px;}
.input-group input:focus{border-color:#ff3333;outline:none;}
button{width:100%;padding:14px;background: linear-gradient(90deg, #ff3333, #ff6600);color:#fff;font-weight:900;border:none;border-radius:8px;cursor:pointer;font-size:15px;margin-top:10px;}
.error{color:#f33;font-size:13px;margin-bottom:10px;text-align:center;background:rgba(255,0,0,0.1);padding:8px;border-radius:5px;}
.link{margin-top:15px;font-size:13px;color:#888;text-align:center;}.link a{color:#ff6600;text-decoration:none;font-weight:bold;}
</style></head><body>
""" + get_bg_html() + """
<div class="box"><h2>JOIN <span>{{panel_name}}</span></h2>{% if error %}<div class="error">{{error}}</div>{% endif %}
<form method="POST">
    <div class="input-group"><label>FULL NAME</label><input type="text" name="name" placeholder="Full Name" required></div>
    <div class="input-group"><label>USERNAME</label><input type="text" name="username" placeholder="Username" required></div>
    <div class="input-group"><label>MOBILE NUMBER</label><input type="text" name="mobile" placeholder="10 Digits Mobile" pattern="[0-9]{10}" required></div>
    <div class="input-group"><label>PASSWORD</label><input type="password" name="password" placeholder="Min 6 characters" minlength="6" required></div>
    <div class="input-group"><label>REFERRAL CODE (Optional)</label><input type="text" name="referral" placeholder="Enter Referral Code (Optional)"></div>
    <button type="submit">Create Account 🚀</button>
</form>
<div class="link">Have account? <a href="/login">Login ➜</a></div></div></body></html>"""

FORGOT = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forgot Password</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}
body{color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}
body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}
.box{background: rgba(15,15,15,0.95);padding:30px 25px;border-radius:16px;max-width:400px;width:100%;border:1px solid #ff3333;}
h2{color:#fff;margin-bottom:20px;text-align:center;letter-spacing:2px;} h2 span{color:#ff6600;}
.input-group{text-align:left;margin-bottom:10px;} .input-group label{font-size:11px;color:#ccc;display:block;margin-bottom:3px;}
.input-group input{width:100%;padding:12px;background:#111;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px;}
.input-group input:focus{border-color:#ff3333;outline:none;}
button{width:100%;padding:14px;background: linear-gradient(90deg, #ff3333, #ff6600);color:#fff;font-weight:900;border:none;border-radius:8px;cursor:pointer;font-size:15px;margin-top:10px;}
.error{color:#f33;font-size:13px;margin-bottom:10px;text-align:center;background:rgba(255,0,0,0.1);padding:8px;border-radius:5px;}
.ok{color:#00e676;font-size:13px;margin-bottom:10px;text-align:center;background:rgba(0,255,102,0.1);padding:8px;border-radius:5px;}
.link{margin-top:15px;font-size:13px;color:#888;text-align:center;}.link a{color:#ff6600;text-decoration:none;font-weight:bold;}
</style></head><body>
""" + get_bg_html() + """
<div class="box"><h2>RESET <span>{{panel_name}}</span> PASS</h2>
{% if error %}<div class="error">{{error}}</div>{% endif %}
{% if ok %}<div class="ok">{{ok}}</div>{% endif %}
<form method="POST">
    <div class="input-group"><label>USERNAME</label><input type="text" name="username" placeholder="Enter Username" required></div>
    <div class="input-group"><label>REGISTERED MOBILE</label><input type="text" name="mobile" placeholder="Enter 10 Digit Mobile" pattern="[0-9]{10}" required></div>
    <div class="input-group"><label>NEW PASSWORD</label><input type="password" name="password" placeholder="New Password (min 6)" minlength="6" required></div>
    <button type="submit">Reset Password 🔓</button>
</form>
<div class="link"><a href="/login">Back to Login</a></div></div></body></html>"""

SUCCESS = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Success</title>
<style>*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}body{color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}.box{background:#0f0f0f;padding:35px 25px;border-radius:16px;max-width:400px;width:100%;border:1px solid #ff3333;text-align:center;}h2{color:#00e676;margin-bottom:20px;}.ref{background:#000;border:2px dashed #ff3333;padding:18px;border-radius:10px;margin:15px 0;}.ref b{font-size:24px;color:#ff6600;letter-spacing:2px;}.btn{display:inline-block;padding:12px 25px;background:#00e676;color:#000;font-weight:800;border-radius:8px;text-decoration:none;margin-top:15px;}</style></head><body>
""" + get_bg_html() + """
<div class="box"><h2>🎉 Account Created!</h2><p style="color:#aaa;">Your Referral Code:</p><div class="ref"><b>{{ref}}</b></div><p style="color:#ffaa00;">💰 Balance: ₹{{bal}}</p><a href="/login" class="btn">Login ➜</a></div></body></html>"""

DASH = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{panel_name}} Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}
body{color:#fff;padding:10px;position:relative;min-height:100vh;overflow-x:hidden;}
body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:-1;}

.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;background:rgba(0,0,0,0.6);padding:10px;border-radius:12px;border:1px solid #333;}
.logo-btn{width:45px;height:45px;background: radial-gradient(circle, #ff0000 0%, #000 70%);border:2px solid #ff3333;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;color:#fff;font-size:22px;box-shadow:0 0 15px rgba(255,51,51,0.5);overflow:hidden;cursor:pointer;transition:0.2s;}
.logo-btn:active{transform:scale(0.95);}
.logo-btn img{width:100%;height:100%;object-fit:cover;}
.wallet{background:rgba(255,51,51,0.15);border:1px solid #ff3333;padding:10px 20px;border-radius:30px;font-weight:800;color:#ff6600;font-size:15px;flex:1;text-align:center;margin:0 10px;box-shadow:inset 0 0 10px rgba(255,51,51,0.2);}
.help-icon{width:35px;height:35px;border-radius:50%;background:#229ED9;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(34,158,217,0.5);text-decoration:none;border:2px solid #fff;}
.help-icon svg{width:20px;height:20px;fill:#fff;}

.sidebar{position:fixed;top:0;left:-320px;width:300px;height:100vh;background:#111;border-right:2px solid #ff3333;z-index:1000;transition:0.3s;padding:20px;box-shadow:5px 0 20px rgba(0,0,0,0.8);overflow-y:auto;}
.sidebar.active{left:0;}
.overlay{position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.7);z-index:999;display:none;}
.overlay.active{display:block;}
.sidebar h2{color:#ff3333;font-size:18px;margin-bottom:20px;border-bottom:1px solid #333;padding-bottom:10px;display:flex;justify-content:space-between;}
.close-btn{cursor:pointer;color:#f33;font-size:20px;}
.sidebar a{display:block;color:#fff;text-decoration:none;padding:15px 10px;border-bottom:1px solid #222;font-size:15px;transition:0.2s;}
.sidebar a:hover{background:#1a1a1a;color:#ff6600;padding-left:15px;}

.card{background: rgba(15,15,15,0.9);border-radius:12px;border:1px solid #ff3333;padding:15px;margin-bottom:15px;box-shadow:0 4px 15px rgba(0,0,0,0.5);}
h1{font-size:22px;color:#fff;text-align:center;margin-bottom:5px;font-weight:800;} h1 span{color:#ff6600;}
.sub{font-size:12px;color:#ff3333;text-align:center;margin-bottom:15px;letter-spacing:1px;}

.search-box{display:flex;background:#000;border:2px solid #333;border-radius:12px;overflow:hidden;transition:0.3s;padding:0; height: 55px;}
.search-box:focus-within{border-color:#ff3333;box-shadow:0 0 15px rgba(255,51,51,0.3);}
.search-icon{background:#111;color:#ff6600;display:flex;align-items:center;justify-content:center;padding:0 12px;font-size:18px;border-right:1px solid #333;}
input[type=text]{flex:1;padding:0 10px;background:transparent;border:none;color:#fff;font-size:14px;outline:none;font-weight:500;min-width:0;}
input[type=text]::placeholder{color:#888;}
.search-btn{background:linear-gradient(135deg, #ff3333, #ff6600);border:none;color:#fff;padding:0 15px;cursor:pointer;font-weight:bold;font-size:14px;transition:0.2s;display:flex;align-items:center;justify-content:center;white-space:nowrap;}
.search-btn:hover{background:linear-gradient(135deg, #ff6600, #ff3333);}

.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.menu-btn{background:#111;border:1px solid #333;padding:15px 10px;border-radius:10px;color:#ccc;text-align:center;font-size:12px;cursor:pointer;font-weight:600;transition:0.2s;display:flex;align-items:center;justify-content:center;gap:5px;}
.menu-btn:hover{border-color:#ff6600;color:#fff;background:#1a1a1a;}
.menu-btn.active{background:linear-gradient(135deg, #ff3333, #ff6600);color:#fff;border-color:#ff6600;box-shadow:0 0 10px rgba(255,102,0,0.5);}
.box-msg{padding:12px;border-radius:8px;margin-bottom:10px;font-size:13px;text-align:center;}
.err{background:rgba(255,51,51,0.1);border:1px solid #f33;color:#f55;}
.ok{background:rgba(0,255,102,0.1);border:1px solid #00e676;color:#00e676;}

.res{
    background: #000; border: 2px solid #00ff66; border-radius: 8px; padding: 15px; max-height: 500px; overflow-y: auto; margin-top: 10px; margin-bottom: 80px;
    font-family: 'Courier New', Courier, monospace; box-shadow: 0 0 20px rgba(0, 255, 102, 0.3); line-height: 1.4; white-space: pre-wrap; font-size: 13px;
}
.res div {font-family: 'Courier New', Courier, monospace !important; word-wrap: break-word;}

.search-more-btn {
    position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #ff3333, #ff6600); color: #fff; padding: 12px 20px; border-radius: 30px;
    font-weight: bold; font-size: 14px; cursor: pointer; box-shadow: 0 4px 15px rgba(255,102,0,0.5); display: flex; align-items: center; gap: 8px;
    z-index: 1000; border: 2px solid #fff; transition: 0.2s;
}
.search-more-btn:hover { transform: scale(1.05); background: linear-gradient(135deg, #ff6600, #ff3333); }

.user-table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px;}
.user-table th, .user-table td{border:1px solid #333;padding:8px;text-align:left;}
.user-table th{background:#1a1a1a;color:#ff6600;}
.user-table tr:nth-child(even){background:#0f0f0f;}
.btn-sm{padding:5px 10px;font-size:11px;border-radius:4px;margin-right:5px;}
.btn-del{background:#ff3333;}
.btn-blk{background:#ff9900;}

.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:2000;justify-content:center;align-items:center;}
.modal-content{background:#111;border:1px solid #ff3333;padding:20px;border-radius:12px;width:90%;max-width:400px;box-shadow:0 0 30px rgba(255,51,51,0.3);}
</style>
<script>
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('active');
    document.getElementById('overlay').classList.toggle('active');
}
function openSettings() { document.getElementById('settingsModal').style.display = 'flex'; }
function closeSettings() { document.getElementById('settingsModal').style.display = 'none'; }
function openUsers() { document.getElementById('usersModal').style.display = 'flex'; }
function closeUsers() { document.getElementById('usersModal').style.display = 'none'; }
function sel(a,p,el){
    document.querySelectorAll('.menu-btn').forEach(b=>b.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('act').value=a;
    document.getElementById('q').placeholder=p;
    document.getElementById('q').focus();
}
function clearResult() {
    window.location.href = '/';
}
</script>
</head><body>

""" + get_bg_html() + """

<div class="overlay" id="overlay" onclick="toggleSidebar()"></div>

{% if adm %}
<div class="sidebar" id="sidebar">
    <h2>👑 ADMIN MENU <span class="close-btn" onclick="toggleSidebar()">✖</span></h2>
    <a href="javascript:void(0)" onclick="toggleSidebar(); openSettings()">⚙️ Panel Settings</a>
    <a href="javascript:void(0)" onclick="toggleSidebar(); openUsers()">👥 User Management</a>
    
    <div style="padding:10px; border-bottom:1px solid #222;">
        <p style="color:#ff6600; font-size:12px; margin-bottom:5px;">🎟️ Generate Ref Code (Amount)</p>
        <form action="/admin/generate_ref_code" method="post" style="display:flex; gap:5px;">
            <input type="number" name="amount" placeholder="Amount ₹" required style="flex:1; padding:8px; background:#000; border:1px solid #333; color:#fff; border-radius:5px; font-size:12px;">
            <button type="submit" style="background:#ff3333; color:#fff; border:none; padding:0 10px; border-radius:5px; font-weight:bold; cursor:pointer;">Create</button>
        </form>
    </div>
    
    <div style="padding:10px; border-bottom:1px solid #222;">
        <p style="color:#ff6600; font-size:12px; margin-bottom:5px;">💰 Add Balance (User)</p>
        <form action="/admin/add_balance" method="post" style="display:flex; flex-direction:column; gap:5px;">
            <input type="text" name="target" placeholder="Username" required style="padding:8px; background:#000; border:1px solid #333; color:#fff; border-radius:5px; font-size:12px;">
            <input type="number" name="amount" placeholder="Amount ₹" required style="padding:8px; background:#000; border:1px solid #333; color:#fff; border-radius:5px; font-size:12px;">
            <button type="submit" style="background:#00b0ff; color:#fff; border:none; padding:8px; border-radius:5px; font-weight:bold; cursor:pointer;">Update Balance</button>
        </form>
    </div>

    <a href="/logout" style="color:#ff3333;">🔒 Logout</a>
</div>
{% endif %}

<div class="top">
    <div class="logo-btn" {% if adm %}onclick="toggleSidebar()"{% endif %}>
        {% if has_logo %}<img src="/static/custom_logo.jpg?t={{time}}">{% else %}R{% endif %}
    </div>
    <div class="wallet">💰 ₹{{wallet}}{% if adm %} (∞){% endif %}</div>
    <a href="{{tg_link}}" target="_blank" class="help-icon">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.96 1.25-5.54 3.69-.52.36-1 .53-1.42.52-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.36-.48.99-.74 3.86-1.68 6.44-2.79 7.73-3.32 3.68-1.53 4.44-1.8 4.94-1.8.11 0 .35.03.51.15.13.09.2.23.22.37.01.1.01.2-.01.27z"/></svg>
    </a>
</div>

<div class="card">
<h1>⚡ <span>{{panel_name}}</span> OSINT ⚡</h1>
<p class="sub">₹{{cost}}/search</p>
<form action="/send" method="post" class="search-box">
    <div class="search-icon">🔍</div>
    <input type="hidden" name="action" id="act" value="{{act}}">
    <input type="text" name="query" id="q" placeholder="{{ph}}" required value="{{qt}}">
    <button type="submit" class="search-btn">Search</button>
</form>
</div>

{% if err %}<div class="box-msg err">{{err}}</div>{% endif %}
{% if ok %}<div class="box-msg ok">{{ok}}</div>{% endif %}

{% if result %}
<div class="res">{{result|safe}}</div>
<div class="search-more-btn" onclick="clearResult()">🔍 Search More</div>
{% endif %}

{% if not result %}
<div class="card">
<div class="grid">
{% for d, a, p in menu %}
<div class="menu-btn {% if a==act %}active{% endif %}" onclick="sel('{{a}}','{{p}}',this)">{{d}}</div>
{% endfor %}
</div>
</div>

<div class="card" style="border-color:#00b0ff;">
<h3 style="color:#00b0ff;margin-bottom:8px;">🎟️ Redeem Code</h3>
<form action="/redeem" method="post" style="display:flex;gap:6px;height:45px;">
<input type="text" name="code" placeholder="Enter Code" required style="border-color:#00b0ff;">
<button type="submit" style="background:linear-gradient(90deg, #00b0ff, #0055ff);padding:0 15px;border-radius:8px;border:none;color:#fff;font-weight:bold;">💵 Redeem</button>
</form>
</div>
{% endif %}

<div style="text-align:center;font-size:10px;color:#666;padding:10px;">POWERED BY {{panel_name}} • MY REF: <b>{{myref}}</b></div>

<div id="settingsModal" class="modal">
    <div class="modal-content">
        <h3 style="color:#ff6600;margin-bottom:15px;">⚙️ Panel Settings</h3>
        <form action="/admin/update_settings" method="post" enctype="multipart/form-data">
            <label style="font-size:12px;color:#ccc;">Panel Name</label>
            <input type="text" name="panel_name" value="{{panel_name}}" style="width:100%;padding:10px;margin-bottom:10px;background:#000;border:1px solid #333;color:#fff;border-radius:5px;">
            <label style="font-size:12px;color:#ccc;">Change Logo (Image)</label>
            <input type="file" name="logo" accept="image/*" style="width:100%;padding:10px;margin-bottom:10px;background:#000;border:1px solid #333;color:#fff;border-radius:5px;">
            <label style="font-size:12px;color:#ccc;">Change Background (Image / MP4 Video)</label>
            <input type="file" name="bg" accept="image/*,video/mp4,video/webm" style="width:100%;padding:10px;margin-bottom:15px;background:#000;border:1px solid #333;color:#fff;border-radius:5px;">
            <button type="submit" style="width:100%;margin-bottom:10px;padding:12px;background:linear-gradient(90deg, #ff3333, #ff6600);color:#fff;border:none;border-radius:8px;font-weight:bold;">Save Changes</button>
            <button type="button" onclick="closeSettings()" style="width:100%;background:#333;padding:12px;color:#fff;border:none;border-radius:8px;">Cancel</button>
        </form>
    </div>
</div>

<div id="usersModal" class="modal">
    <div class="modal-content" style="max-width:800px;overflow-y:auto;max-height:90vh;">
        <div style="display:flex;justify-content:space-between;margin-bottom:15px;">
            <h3 style="color:#ff6600;">👥 User Management</h3>
            <button onclick="closeUsers()" style="background:#333;color:#fff;padding:5px 10px;border:none;border-radius:5px;">✖</button>
        </div>
        <table class="user-table">
            <tr><th>Name</th><th>User</th><th>Mobile</th><th>Password</th><th>Wallet</th><th>Status</th><th>Action</th></tr>
            {% for u in all_users %}
            <tr>
                <td>{{u['name']}}</td>
                <td>{{u['username']}}</td>
                <td>{{u['mobile']}}</td>
                <td>{{u['raw_password']}}</td>
                <td>₹{{u['wallet']}}</td>
                <td>{% if u['is_blocked'] == 1 %}<span style="color:red;">Blocked</span>{% else %}<span style="color:#00e676;">Active</span>{% endif %}</td>
                <td>
                    {% if u['is_admin'] == 0 %}
                    <a href="/admin/toggle_block/{{u['username']}}" class="btn-sm btn-blk" style="text-decoration:none;color:#000;">{% if u['is_blocked'] == 1 %}Unblock{% else %}Block{% endif %}</a>
                    <a href="/admin/delete_user/{{u['username']}}" class="btn-sm btn-del" style="text-decoration:none;color:#fff;" onclick="return confirm('Pakka delete karna hai?')">Delete</a>
                    {% else %}<span style="color:#888;">Admin</span>{% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
</div>
</body></html>"""

def page(user, act="", ph="Enter value...", qt="", err=None, ok=None, result=None):
    all_users = []
    if user and user['is_admin']:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        all_users = c.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
        c.close()

    return render_template_string(DASH, 
        wallet=(user['wallet'] if not user['is_admin'] else "∞"), 
        adm=bool(user['is_admin']), 
        myref=user['referral_code'], 
        menu=MENU, act=act, ph=ph, qt=qt, cost=SEARCH_COST, err=err, ok=ok, result=result, 
        has_logo=os.path.exists(LOGO_FILE), time=datetime.now().timestamp(),
        panel_name=get_setting('panel_name'), all_users=all_users, tg_link=TG_HELP_ID
    )

# ================= ROUTES =================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        usr = get_user(u)
        if usr and check_password_hash(usr['password_hash'], p):
            if usr['is_blocked'] == 1:
                return render_template_string(LOGIN, error="Your account is blocked!", has_logo=os.path.exists(LOGO_FILE), tg_link=TG_HELP_ID, time=datetime.now().timestamp(), panel_name=get_setting('panel_name'))
            session['u'] = u
            return redirect('/')
        return render_template_string(LOGIN, error="Invalid credentials", has_logo=os.path.exists(LOGO_FILE), tg_link=TG_HELP_ID, time=datetime.now().timestamp(), panel_name=get_setting('panel_name'))
    return render_template_string(LOGIN, has_logo=os.path.exists(LOGO_FILE), tg_link=TG_HELP_ID, time=datetime.now().timestamp(), panel_name=get_setting('panel_name'))

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name'].strip()
        u = request.form['username'].strip()
        mob = request.form['mobile'].strip()
        p = request.form['password']
        ref_by = request.form.get('referral', '').strip()
        
        c = sqlite3.connect(DB)
        if c.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone():
            c.close()
            return render_template_string(SIGNUP, error="Username already exists!", panel_name=get_setting('panel_name'))
        
        referrer_user = None
        referrer_admin_code = None
        
        if ref_by != "":
            referrer_user = c.execute("SELECT username FROM users WHERE referral_code=?", (ref_by,)).fetchone()
            if not referrer_user:
                referrer_admin_code = c.execute("SELECT amount, code FROM redeem_codes WHERE code=? AND status='active'", (ref_by,)).fetchone()
            
            if not referrer_user and not referrer_admin_code:
                c.close()
                return render_template_string(SIGNUP, error="Invalid Referral Code!", panel_name=get_setting('panel_name'))
        
        my_ref = gen_ref()
        start_bal = SIGNUP_BONUS
        
        if referrer_admin_code:
            start_bal += referrer_admin_code[0]
            c.execute("UPDATE redeem_codes SET status='used', used_by=? WHERE code=?", (u, ref_by))
            
        c.execute("INSERT INTO users(name,username,mobile,password_hash,raw_password,referral_code,referred_by,wallet,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (name, u, mob, generate_password_hash(p), p, my_ref, ref_by if ref_by else None, start_bal, datetime.now().isoformat()))
        
        if referrer_user:
            c.execute("UPDATE users SET wallet=wallet+? WHERE username=?", (REFERRAL_BONUS, referrer_user[0]))
            
        c.commit(); c.close()
        return render_template_string(SUCCESS, ref=my_ref, bal=start_bal)
    return render_template_string(SIGNUP, panel_name=get_setting('panel_name'))

@app.route('/forgot', methods=['GET','POST'])
def forgot():
    if request.method == 'POST':
        u = request.form['username'].strip()
        mob = request.form['mobile'].strip()
        new_p = request.form['password']
        
        c = sqlite3.connect(DB)
        user = c.execute("SELECT id FROM users WHERE username=? AND mobile=?", (u, mob)).fetchone()
        
        if user:
            c.execute("UPDATE users SET password_hash=?, raw_password=? WHERE username=?", (generate_password_hash(new_p), new_p, u))
            c.commit()
            c.close()
            return render_template_string(FORGOT, ok="✅ Password reset successfully!", panel_name=get_setting('panel_name'))
        else:
            c.close()
            return render_template_string(FORGOT, error="❌ Invalid Username or Mobile!", panel_name=get_setting('panel_name'))
    return render_template_string(FORGOT, panel_name=get_setting('panel_name'))

@app.route('/logout')
def logout():
    session.pop('u', None)
    return redirect('/login')

@app.route('/')
def index():
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    if not user: return redirect('/login')
    return page(user)

@app.route('/send', methods=['POST'])
def send():
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    act = request.form['action']
    qt = request.form['query'].strip()
    
    if not user['is_admin'] and user['wallet'] < SEARCH_COST:
        return page(user, err="Insufficient Balance!")
        
    with lock:
        r = asyncio.run_coroutine_threadsafe(send_wait(act, qt), loop).result()
        
    if not user['is_admin'] and r:
        update_wallet(session['u'], -SEARCH_COST)
        user = get_user(session['u'])

    res_html = wm(extract_text(r)) if r else "❌ Bot response timeout. Target bot is not replying."
    
    if not extract_text(r):
        res_html = "❌ No data found or Bot is busy."
        
    return page(user, act=act, qt=qt, result=res_html)

@app.route('/redeem', methods=['POST'])
def redeem():
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    code = request.form['code'].strip()
    
    c = sqlite3.connect(DB)
    row = c.execute("SELECT amount FROM redeem_codes WHERE code=? AND status='active'", (code,)).fetchone()
    
    if row:
        c.execute("UPDATE redeem_codes SET status='used', used_by=? WHERE code=?", (session['u'], code))
        c.commit()
        update_wallet(session['u'], row[0])
        c.close()
        return page(get_user(session['u']), ok="✅ Code Redeemed! ₹" + str(row[0]) + " Added.")
    c.close()
    return page(user, err="❌ Invalid or Used Code.")

# ================= ADMIN ROUTES =================
@app.route('/admin/update_settings', methods=['POST'])
def update_settings():
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    if not user['is_admin']: return redirect('/')
    
    new_name = request.form.get('panel_name', '').strip()
    if new_name:
        set_setting('panel_name', new_name)
        
    if 'logo' in request.files:
        file = request.files['logo']
        if file.filename != '': file.save(LOGO_FILE)
            
    if 'bg' in request.files:
        file = request.files['bg']
        if file.filename != '': 
            file.save(BG_FILE)
            ext = file.filename.rsplit('.', 1)[-1].lower()
            with open(BG_EXT_FILE, 'w') as f:
                f.write(ext)
            
    return page(user, ok="✅ Panel Settings Updated Successfully!")

@app.route('/admin/generate_ref_code', methods=['POST'])
def admin_generate_ref_code():
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    if not user['is_admin']: return redirect('/')
    
    amt = request.form['amount']
    code = "RICH-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO redeem_codes(code, amount, created_by, created_at) VALUES(?,?,?,?)", (code, amt, session['u'], datetime.now().isoformat()))
    c.commit(); c.close()
    return page(user, ok=f"✅ Ref Code Created: {code} (Amount: ₹{amt})")

@app.route('/admin/add_balance', methods=['POST'])
def add_balance():
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    if not user['is_admin']: return redirect('/')
    
    target = request.form['target'].strip()
    amt = float(request.form['amount'])
    
    c = sqlite3.connect(DB)
    row = c.execute("SELECT wallet FROM users WHERE username=?", (target,)).fetchone()
    if row:
        c.execute("UPDATE users SET wallet=? WHERE username=?", (amt, target))
        c.commit()
        c.close()
        return page(user, ok=f"✅ {target} ka balance ₹{amt} set kar diya gaya hai.")
    c.close()
    return page(user, err=f"❌ User {target} nahi mila!")

@app.route('/admin/toggle_block/<target>')
def toggle_block(target):
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    if not user['is_admin'] or target == WEB_USER: return redirect('/')
    
    c = sqlite3.connect(DB)
    curr = c.execute("SELECT is_blocked FROM users WHERE username=?", (target,)).fetchone()
    if curr:
        new_status = 0 if curr[0] == 1 else 1
        c.execute("UPDATE users SET is_blocked=? WHERE username=?", (new_status, target))
        c.commit()
    c.close()
    return page(user, ok="✅ User " + target + " status updated.")

@app.route('/admin/delete_user/<target>')
def delete_user(target):
    if 'u' not in session: return redirect('/login')
    user = get_user(session['u'])
    if not user['is_admin'] or target == WEB_USER: return redirect('/')
    
    c = sqlite3.connect(DB)
    c.execute("DELETE FROM users WHERE username=?", (target,))
    c.commit(); c.close()
    return page(user, ok="✅ User " + target + " deleted successfully.")

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    print("🌐 Web Server Started on http://127.0.0.1:7860")
    app.run(host='0.0.0.0', port=7860, debug=False, use_reloader=False)