import os, sys, time, sqlite3, datetime, threading
from flask import Flask, jsonify, request, render_template
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN, ADMIN_ID = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_ADMIN_ID")
app = Flask(__name__)

def db_query(query, params=(), fetch_all=False, fetch_one=False, commit=False):
    conn = sqlite3.connect('bot_business.db', timeout=30.0)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchall() if fetch_all else (cursor.fetchone() if fetch_one else None)
    if commit: conn.commit()
    conn.close()
    return result

def init_db():
    conn = sqlite3.connect('bot_business.db', timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0, phone_number TEXT, active_video_id INTEGER DEFAULT NULL, click_timestamp REAL DEFAULT 0.0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS video_tasks (video_id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, max_views INTEGER, current_views INTEGER DEFAULT 0, watch_time INTEGER DEFAULT 30, status TEXT DEFAULT 'active')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS affiliate_links (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, cashback_amount REAL DEFAULT 50.0, status TEXT DEFAULT 'active')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS view_logs (user_id INTEGER, video_id INTEGER, PRIMARY KEY (user_id, video_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS transaction_ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, description TEXT, amount REAL, log_date TEXT)''')
    conn.commit(); conn.close()

@app.route('/')
def index_portal(): return render_template('index.html')

@app.route('/api/user/<int:uid>', methods=['GET'])
def get_user_profile(uid):
    data = db_query("SELECT balance, phone_number, username FROM users WHERE user_id=?", (uid,), fetch_one=True)
    if not data: return jsonify({"balance": 0.0, "phone": "", "username": "Guest"})
    return jsonify({"balance": data, "phone": data or "", "username": data or "User"})

@app.route('/api/tasks/<int:uid>', methods=['GET'])
def get_tasks(uid):
    tasks = db_query("SELECT video_id, url, watch_time FROM video_tasks WHERE status='active' AND current_views < max_views AND video_id NOT IN (SELECT video_id FROM view_logs WHERE user_id=?)", (uid,), fetch_all=True)
    aff = db_query("SELECT url, cashback_amount FROM affiliate_links WHERE status='active' ORDER BY id DESC LIMIT 1", fetch_one=True)
    return jsonify({"videos": [{"id": t, "url": t, "time": t} for t in tasks], "affiliate": {"url": aff if aff else "https://your-jumia-affiliate-link.com", "reward": aff if aff else 50.0}})

@app.route('/api/ledger/<int:uid>', methods=['GET'])
def get_user_ledger(uid):
    logs = db_query("SELECT type, description, amount, log_date FROM transaction_ledger WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,), fetch_all=True)
    return jsonify([{"type": l, "description": l, "amount": l, "date": l} for l in logs])

@app.route('/api/click', methods=['POST'])
def register_click():
    req = request.json; db_query("UPDATE users SET active_video_id=?, click_timestamp=? WHERE user_id=?", (req.get('video_id'), time.time(), req.get('user_id')), commit=True)
    return jsonify({"status": "success"})

@app.route('/api/verify', methods=['POST'])
def verify_watch():
    req = request.json; uid, vid = req.get('user_id'), req.get('video_id')
    task = db_query("SELECT watch_time, current_views, max_views FROM video_tasks WHERE video_id=?", (vid,), fetch_one=True)
    profile = db_query("SELECT click_timestamp, active_video_id FROM users WHERE user_id=?", (uid,), fetch_one=True)
    if not task or not profile or profile != vid: return jsonify({"status": "error", "msg": "❌ Verification log error."})
    if task[1] >= task[2]: return jsonify({"status": "error", "msg": "❌ Campaign views quota hit completely."})
    if (time.time() - profile[0]) < float(task[0]): return jsonify({"status": "error", "msg": "🛑 Watch timer error! Keep watching."})
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    db_query("UPDATE users SET balance = balance + 2.0, active_video_id=NULL WHERE user_id=?", (uid,), commit=True)
    db_query("INSERT INTO view_logs (user_id, video_id) VALUES (?, ?)", (uid, vid), commit=True)
    db_query("UPDATE video_tasks SET current_views = current_views + 1 WHERE video_id=?", (vid,), commit=True)
    db_query("INSERT INTO transaction_ledger (user_id, type, description, amount, log_date) VALUES (?, 'credit', ?, 2.0, ?)", (uid, f"Watched Video Promo #{vid}", now_str), commit=True)
    limits = db_query("SELECT current_views, max_views FROM video_tasks WHERE video_id=?", (vid,), fetch_one=True)
    if limits and limits[0] >= limits[1]: db_query("UPDATE video_tasks SET status='completed' WHERE video_id=?", (vid,), commit=True)
    return jsonify({"status": "success", "msg": "🎉 Credit Approved! + KSh 2.00 allocated."})

@app.route('/api/withdraw', methods=['POST'])
def process_payout():
    req = request.json; uid, phone = req.get('user_id'), req.get('phone')
    bal = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), fetch_one=True)
    if not bal or bal[0] < 100.0: return jsonify({"status": "error", "msg": "❌ Payout requires KSh 100 minimum balance."})
    db_query("UPDATE users SET phone_number=? WHERE user_id=?", (phone, uid), commit=True)
    return jsonify({"status": "success", "msg": f"✅ Withdrawal request filed for line {phone}!"})

@app.route('/api/admin/dashboard', methods=['GET'])
def get_admin_dashboard():
    if request.args.get('password') != "Money": return jsonify({"error": "Unauthorized"}), 401
    campaigns = db_query("SELECT video_id, url, current_views, max_views, watch_time FROM video_tasks WHERE status='active'", fetch_all=True)
    payouts = db_query("SELECT user_id, phone_number, balance, username FROM users WHERE balance >= 100.0 AND phone_number IS NOT NULL", fetch_all=True)
    return jsonify({"campaigns": [{"id": c[0], "url": c[1], "current": c[2], "max": c[3], "time": c[4]} for c in campaigns], "payouts": [{"id": p[0], "phone": p[1], "balance": p[2], "username": p[3] or "User"} for p in payouts]})

@app.route('/api/admin/add_video', methods=['POST'])
def admin_add_video():
    req = request.json; if req.get('password') != "Money": return jsonify({"error": "Error"}), 401
    db_query("INSERT INTO video_tasks (url, max_views, watch_time) VALUES (?, ?, ?)", (req.get('url'), req.get('max_views'), req.get('watch_time')), commit=True)
    return jsonify({"status": "success"})

@app.route('/api/admin/add_affiliate', methods=['POST'])
def admin_add_affiliate():
    req = request.json; if req.get('password') != "Money": return jsonify({"error": "Error"}), 401
    db_query("UPDATE affiliate_links SET status='inactive'", commit=True)
    db_query("INSERT INTO affiliate_links (url, cashback_amount) VALUES (?, ?)", (req.get('url'), req.get('reward')), commit=True)
    return jsonify({"status": "success"})

@app.route('/api/admin/delete_video', methods=['POST'])
def admin_delete_video():
    req = request.json; if req.get('password') != "Money": return jsonify({"error": "Error"}), 401
    db_query("UPDATE video_tasks SET status='completed' WHERE video_id=?", (req.get('video_id'),), commit=True)
    return jsonify({"status": "success"})

@app.route('/api/admin/settle_user', methods=['POST'])
def admin_settle_user():
    req = request.json; if req.get('password') != "Money": return jsonify({"error": "Error"}), 401
    uid = req.get('user_id'); bal = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), fetch_one=True)
    if bal:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        db_query("INSERT INTO transaction_ledger (user_id, type, description, amount, log_date) VALUES (?, 'withdrawal', ?, ?, ?)", (uid, f"Extracted direct to MiniPay", bal[0], now_str), commit=True)
        db_query("UPDATE users SET balance = 0.0 WHERE user_id=?", (uid,), commit=True)
    return jsonify({"status": "success"})

async def post_init(application): await application.bot.set_my_commands([BotCommand("start", "📱 Launch Cash Application Portal")])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; db_query("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username), commit=True)
    LIVE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
    nav = [[InlineKeyboardButton("📱 Open Cash Dashboard MiniApp", web_app=WebAppInfo(url=LIVE_URL))]]
    await update.message.reply_text(f"👋 Mambo {user.first_name}!\nTap below to check balances inside your mini wallet portal:", reply_markup=InlineKeyboardMarkup(nav))

def launch_bot():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).connect_timeout(60.0).read_timeout(60.0).pool_timeout(60.0).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command)); app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    init_db(); t = threading.Thread(target=launch_bot); t.daemon = True; t.start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
