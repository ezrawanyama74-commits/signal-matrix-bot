import sys
import time
import logging
import sqlite3
from flask import Flask, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def init_db():
    conn = sqlite3.connect('bot_business.db', timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0, phone_number TEXT, active_video_id INTEGER DEFAULT NULL, click_timestamp REAL DEFAULT 0.0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS video_tasks (video_id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, max_views INTEGER, current_views INTEGER DEFAULT 0, watch_time INTEGER DEFAULT 30, status TEXT DEFAULT 'active')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS affiliate_links (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, cashback_amount REAL DEFAULT 50.0, status TEXT DEFAULT 'active')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS view_logs (user_id INTEGER, video_id INTEGER, PRIMARY KEY (user_id, video_id))''')
    conn.commit()
    conn.close()

def db_query(query, params=(), fetch_all=False, fetch_one=False, commit=False):
    conn = sqlite3.connect('bot_business.db', timeout=30.0)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = None
    if fetch_all: result = cursor.fetchall()
    elif fetch_one: result = cursor.fetchone()
    if commit: conn.commit()
    conn.close()
    return result

init_db()
print("\n" + "═"*60)
print(" 🚀 RESILIENT NETWORK ENGINE CONNECTING... ")
print("═"*60)
TOKEN = input("🔑 Paste your BotFather Telegram Token: ").strip()
ADMIN_ID = input("🆔 Paste your Personal Numeric User ID: ").strip()

if not TOKEN or not ADMIN_ID:
    print("❌ Error: Missing credentials.")
    sys.exit(1)

ADMIN_ID = int(ADMIN_ID)

web_app = Flask(__name__)

@web_app.route('/api/user/<int:uid>', methods=['GET'])
def get_user_profile(uid):
    data = db_query("SELECT balance, phone_number, username FROM users WHERE user_id=?", (uid,), fetch_one=True)
    if not data: return jsonify({"balance": 0.0, "phone": "", "username": "Guest"})
    return jsonify({"balance": data[0], "phone": data[1] or "", "username": data[2] or "User"})

@web_app.route('/api/tasks/<int:uid>', methods=['GET'])
def get_tasks(uid):
    tasks = db_query("SELECT video_id, url, watch_time FROM video_tasks WHERE status='active' AND current_views < max_views AND video_id NOT IN (SELECT video_id FROM view_logs WHERE user_id=?)", (uid,), fetch_all=True)
    aff = db_query("SELECT url, cashback_amount FROM affiliate_links WHERE status='active' LIMIT 1", fetch_one=True)
    task_list = [{"id": t[0], "url": t[1], "time": t[2]} for t in tasks]
    aff_deal = {"url": aff[0], "reward": aff[1]} if aff else {"url": "#", "reward": 0.0}
    return jsonify({"videos": task_list, "affiliate": aff_deal})

@web_app.route('/api/click', methods=['POST'])
def register_click():
    req = request.json
    uid, vid = req.get('user_id'), req.get('video_id')
    db_query("UPDATE users SET active_video_id=?, click_timestamp=? WHERE user_id=?", (vid, time.time(), uid), commit=True)
    return jsonify({"status": "success"})

@web_app.route('/api/verify', methods=['POST'])
def verify_watch():
    req = request.json
    uid, vid = req.get('user_id'), req.get('video_id')
    task = db_query("SELECT watch_time, current_views, max_views FROM video_tasks WHERE video_id=?", (vid,), fetch_one=True)
    profile = db_query("SELECT click_timestamp, active_video_id FROM users WHERE user_id=?", (uid,), fetch_one=True)
    
    if not task or not profile or profile[1] != vid:
        return jsonify({"status": "error", "msg": "Invalid tracking sequence."})
    if task[1] >= task[2]:
        return jsonify({"status": "error", "msg": "Campaign limit reached!"})
        
    elapsed = time.time() - profile[0]
    if elapsed < float(task[0]):
        return jsonify({"status": "error", "msg": f"Please watch for {int(task[0] - elapsed)} more seconds."})
        
    db_query("UPDATE users SET balance = balance + 2.0, active_video_id=NULL WHERE user_id=?", (uid,), commit=True)
    db_query("INSERT INTO view_logs (user_id, video_id) VALUES (?, ?)", (uid, vid), commit=True)
    db_query("UPDATE video_tasks SET current_views = current_views + 1 WHERE video_id=?", (vid,), commit=True)
    return jsonify({"status": "success", "msg": "Approved! + KSh 2.00"})

@web_app.route('/api/withdraw', methods=['POST'])
def process_payout():
    req = request.json
    uid, phone = req.get('user_id'), req.get('phone')
    bal = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), fetch_one=True)
    if not bal or bal[0] < 100.0: return jsonify({"status": "error", "msg": "Minimum payout requirement is KSh 100."})
    db_query("UPDATE users SET phone_number=? WHERE user_id=?", (phone, uid), commit=True)
    return jsonify({"status": "success", "msg": f"Withdrawal request logged for account {phone}!"})

def run_web():
    web_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# --- HTML WALLET UI BUILDER ---
import os
os.makedirs('templates', exist_ok=True)
with open('templates/index.html', 'w') as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cash Engine Wallet</title>
    <script src="https://telegram.org"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0e1621; color: #fff; margin: 0; padding: 15px; text-align: center; }
        .card { background: linear-gradient(135deg, #1c92d2, #f2fcfe); color: #000; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); text-align: left; }
        .balance-title { font-size: 14px; opacity: 0.8; font-weight: bold; }
        .balance-value { font-size: 32px; font-weight: bold; margin-top: 5px; }
        .section-title { text-align: left; font-size: 18px; font-weight: bold; margin: 20px 0 10px 0; color: #3498db; }
        .btn { display: block; width: 100%; padding: 12px; background: #2481cc; border: none; color: #fff; border-radius: 10px; font-weight: bold; font-size: 16px; cursor: pointer; text-decoration: none; margin-top: 10px; box-sizing: border-box; }
        .task-card { background: #17212b; padding: 15px; border-radius: 10px; margin-bottom: 10px; text-align: left; border: 1px solid #242f3d; }
        input { width: 100%; padding: 12px; border-radius: 10px; border: 1px solid #242f3d; background: #17212b; color: #fff; box-sizing: border-box; font-size: 16px; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="balance-title">💰 TOTAL ACTIVE WALLET</div>
        <div id="balance" class="balance-value">KSh 0.00</div>
        <div style="font-size:12px; opacity:0.6; margin-top:5px;" id="username">Loading...</div>
    </div>
    <div class="section-title">📺 Video Monetization Tasks</div>
    <div id="video-container"></div>
    <div class="section-title">🛍️ Shopping Cashback</div>
    <div class="task-card">
        <div style="font-weight:bold;">Shop & Claim Cashback</div>
        <div style="font-size:13px; color:#aaa; margin:5px 0;" id="aff-reward">Earn rewards on deals.</div>
        <a id="aff-link" class="btn" style="background:#27ae60;" target="_blank">Shop Network Deals</a>
    </div>
    <div class="section-title">💸 Payout Settlements</div>
    <div class="task-card">
        <label style="font-size:13px; color:#aaa;">MiniPay Registered Mobile Number</label>
        <input type="tel" id="phone-input" placeholder="e.g. 0702326612">
        <button class="btn" style="background:#e74c3c;" onclick="requestWithdrawal()">Extract Cash to MiniPay</button>
    </div>
    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 12345;
        const API_BASE = window.location.origin;
        async function loadDashboard() {
            try {
                let pRes = await fetch(`${API_BASE}/api/user/${uid}`);
                let pData = await pRes.json();
                document.getElementById('balance').innerText = `KSh ${pData.balance.toFixed(2)}`;
                document.getElementById('phone-input').value = pData.phone;
                document.getElementById('username').innerText = `Account Identity: @${pData.username}`;
                let tRes = await fetch(`${API_BASE}/api/tasks/${uid}`);
                let tData = await tRes.json();
                let vDiv = document.getElementById('video-container');
                vDiv.innerHTML = '';
                if(tData.videos.length === 0) { vDiv.innerHTML = '<div style="color:#aaa; font-size:14px; padding:10px;">No ads available right now.</div>'; }
                tData.videos.forEach(v => {
                    vDiv.innerHTML += `
                        <div class="task-card">
                            <div style="font-weight:bold;">Watch Campaign Asset #${v.id}</div>
                            <div style="font-size:12px; color:#aaa; margin-bottom:8px;">Required: ${v.time} seconds</div>
                            <button class="btn" onclick="startVideo(${v.id}, '${v.url}')">1. Open Video Stream</button>
                            <button class="btn" style="background:#8e44ad;" onclick="verifyVideo(${v.id})">2. Verify & Claim</button>
                        </div>`;
                });
                document.getElementById('aff-link').href = tData.affiliate.url;
                document.getElementById('aff-reward').innerText = `Earn KSh ${tData.affiliate.reward.toFixed(2)} cashback on orders.`;
            } catch(e) { console.error(e); }
        }
        async function startVideo(vid, url) {
            await fetch(`${API_BASE}/api/click`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: uid, video_id: vid}) });
            window.open(url, '_blank');
        }
        async function verifyVideo(vid) {
            let res = await fetch(`${API_BASE}/api/verify`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: uid, video_id: vid}) });
            let data = await res.json();
            alert(data.msg);
            loadDashboard();
        }
        async function requestWithdrawal() {
            let phone = document.getElementById('phone-input').value.trim();
            if(!phone) { alert("Please input a number."); return; }
            let res = await fetch(`${API_BASE}/api/withdraw`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: uid, phone: phone}) });
            let data = await res.json();
            alert(data.msg);
            loadDashboard();
        }
        loadDashboard();
    </script>
</body>
</html>''')

async def post_init(application):
    await application.bot.set_my_commands([BotCommand("start", "🚀 Launch Mini Wallet App")])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_query("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username), commit=True)
    # Paste your live tunnel address string (e.g. from local tunnels/Ngrok) below
    MINI_APP_URL = "https://ngrok-free.app"
    nav = [[InlineKeyboardButton("📱 Open Cash Dashboard MiniApp", web_app=WebAppInfo(url=MINI_APP_URL))]]
    await update.message.reply_text(f"👋 Mambo {user.first_name}!\nTap the portal button below to use your beautiful mini wallet interface:", reply_markup=InlineKeyboardMarkup(nav))

def launch_bot():
    # FIXED: Added connection_pool_size, read_timeout, and connect_timeout protections to stop ConnectTimeout crashes
    app = Application.builder().token(TOKEN).connect_timeout(60.0).read_timeout(60.0).pool_timeout(60.0).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command))
    print("🤖 Bot engine securely online.")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    print("🌐 Local Web App API endpoint streaming live on port 5000.")
    launch_bot()
