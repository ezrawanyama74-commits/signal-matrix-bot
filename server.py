import os
import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates', static_folder='templates')

DB_URL = os.environ.get('DATABASE_URL')
psycopg2 = None

if DB_URL:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        psycopg2 = None

def get_db():
    if DB_URL and psycopg2:
        return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    
    conn = sqlite3.connect("local_test.db")
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = get_db()
    cur = conn.cursor()
    
    is_sqlite = not (DB_URL and psycopg2)
    if is_sqlite:
        query = query.replace("%s", "?")
        if " RETURNING " in query:
            query = query.split(" RETURNING ")[0]

    cur.execute(query, params)
    result = None
    
    if fetchone:
        row = cur.fetchone()
        result = dict(row) if row else None
    elif fetchall:
        rows = cur.fetchall()
        result = [dict(r) for r in rows] if rows else []

    if commit or query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE")):
        conn.commit()

    cur.close()
    conn.close()
    return result

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    is_sqlite = not (DB_URL and psycopg2)
    if is_sqlite:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone_number TEXT,
                balance REAL DEFAULT 0.00,
                is_pro INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                minipay_wallet TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                video_url TEXT NOT NULL,
                reward_kes REAL DEFAULT 2.00,
                duration_sec INTEGER DEFAULT 15,
                is_pro_only INTEGER DEFAULT 0
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                task_id INTEGER,
                UNIQUE(telegram_id, task_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                mpesa_receipt TEXT,
                amount REAL,
                type TEXT,
                status TEXT DEFAULT 'pending'
            );
        """)
        cur.execute("DELETE FROM tasks;")
        cur.execute("""
            INSERT INTO tasks (title, video_url, reward_kes, duration_sec, is_pro_only) VALUES
            ('Watch LipaViews Free Task', 'https://www.youtube.com/embed/M7lc1UVf-VE', 2.00, 15, 0),
            ('Watch Sponsored Promo Video', 'https://www.youtube.com/embed/dQw4w9WgXcQ', 2.00, 15, 0),
            ('PRO Task: Premium Partner Review', 'https://www.youtube.com/embed/M7lc1UVf-VE', 15.00, 15, 1);
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                full_name TEXT,
                phone_number TEXT,
                balance NUMERIC(10,2) DEFAULT 0.00,
                is_pro BOOLEAN DEFAULT FALSE,
                referral_code TEXT UNIQUE,
                minipay_wallet TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                video_url TEXT NOT NULL,
                reward_kes NUMERIC(10,2) DEFAULT 2.00,
                duration_sec INT DEFAULT 15,
                is_pro_only BOOLEAN DEFAULT FALSE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT REFERENCES users(telegram_id),
                task_id INT REFERENCES tasks(id),
                CONSTRAINT unique_user_task UNIQUE (telegram_id, task_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                mpesa_receipt TEXT,
                amount NUMERIC(10,2),
                type VARCHAR(20),
                status VARCHAR(20) DEFAULT 'pending'
            );
        """)
        cur.execute("DELETE FROM tasks;")
        cur.execute("""
            INSERT INTO tasks (title, video_url, reward_kes, duration_sec, is_pro_only) VALUES
            ('Watch LipaViews Free Task', 'https://www.youtube.com/embed/M7lc1UVf-VE', 2.00, 15, FALSE),
            ('Watch Sponsored Promo Video', 'https://www.youtube.com/embed/dQw4w9WgXcQ', 2.00, 15, FALSE),
            ('PRO Task: Premium Partner Review', 'https://www.youtube.com/embed/M7lc1UVf-VE', 15.00, 15, TRUE);
        """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- USER ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    full_name = data.get('full_name')
    phone = data.get('phone_number')

    if not full_name or not phone:
        return jsonify({"error": "Original ID Name and Phone Number are required"}), 400

    user = execute_query("SELECT * FROM users WHERE telegram_id = %s", (tg_id,), fetchone=True)

    if not user:
        ref_code = f"ref_{tg_id}"
        execute_query("""
            INSERT INTO users (telegram_id, full_name, phone_number, referral_code)
            VALUES (%s, %s, %s, %s);
        """, (tg_id, full_name, phone, ref_code), commit=True)
    else:
        execute_query("""
            UPDATE users SET full_name = %s, phone_number = %s WHERE telegram_id = %s;
        """, (full_name, phone, tg_id), commit=True)

    user = execute_query("SELECT * FROM users WHERE telegram_id = %s", (tg_id,), fetchone=True)
    return jsonify({"status": "success", "user": user})

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tg_id = request.args.get('telegram_id')
    user = execute_query("SELECT * FROM users WHERE telegram_id = %s", (tg_id,), fetchone=True)
    is_pro = bool(user['is_pro']) if user else False

    if is_pro:
        query = """
            SELECT t.*, CASE WHEN tc.id IS NOT NULL THEN 1 ELSE 0 END AS completed
            FROM tasks t LEFT JOIN task_completions tc ON t.id = tc.task_id AND tc.telegram_id = %s;
        """
        tasks = execute_query(query, (tg_id,), fetchall=True)
    else:
        query = """
            SELECT t.*, CASE WHEN tc.id IS NOT NULL THEN 1 ELSE 0 END AS completed
            FROM tasks t LEFT JOIN task_completions tc ON t.id = tc.task_id AND tc.telegram_id = %s
            WHERE t.is_pro_only = 0 OR t.is_pro_only = FALSE;
        """
        tasks = execute_query(query, (tg_id,), fetchall=True)

    return jsonify({"tasks": tasks, "is_pro": is_pro})

@app.route('/api/claim-reward', methods=['POST'])
def claim_reward():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    task_id = data.get('task_id')

    existing = execute_query(
        "SELECT id FROM task_completions WHERE telegram_id = %s AND task_id = %s",
        (tg_id, task_id), fetchone=True
    )
    if existing:
        return jsonify({"error": "Task already completed"}), 400

    execute_query("INSERT INTO task_completions (telegram_id, task_id) VALUES (%s, %s);", (tg_id, task_id), commit=True)
    task = execute_query("SELECT reward_kes FROM tasks WHERE id = %s;", (task_id,), fetchone=True)
    reward = task['reward_kes']

    execute_query("UPDATE users SET balance = balance + %s WHERE telegram_id = %s;", (reward, tg_id), commit=True)
    user = execute_query("SELECT balance FROM users WHERE telegram_id = %s;", (tg_id,), fetchone=True)

    return jsonify({"message": f"Claimed KES {reward:.2f}!", "new_balance": float(user['balance'])})

@app.route('/api/withdraw-minipay', methods=['POST'])
def withdraw_minipay():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    wallet = data.get('minipay_wallet')

    user = execute_query("SELECT balance FROM users WHERE telegram_id = %s;", (tg_id,), fetchone=True)

    if not user or float(user['balance']) < 130.00:
        return jsonify({"error": "Insufficient Balance. Minimum withdrawal is 100% $1 USD (KES 130.00)"}), 400

    execute_query("UPDATE users SET balance = balance - 130.00, minipay_wallet = %s WHERE telegram_id = %s;", (wallet, tg_id), commit=True)
    execute_query("INSERT INTO transactions (telegram_id, amount, type, status) VALUES (%s, 130.00, 'minipay_withdraw', 'processed');", (tg_id,), commit=True)
    
    return jsonify({"message": "$1.00 USD successfully withdrawn to MiniPay wallet!"})

# --- ADMIN PANEL ROUTES ---
@app.route('/admin')
def admin_panel():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LipaViews Admin</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: white; padding: 16px; margin:0; }
            h2 { color: #38bdf8; margin-bottom: 4px; }
            .card { background: #1e293b; padding: 12px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #334155; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
            th, td { border: 1px solid #334155; padding: 8px; text-align: left; }
            th { background: #0f172a; color: #38bdf8; }
            .btn { background: #16a34a; color: white; border: none; padding: 6px 10px; cursor: pointer; border-radius: 4px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h2>LipaViews Admin Portal</h2>
        <div class="card">
            <p style="margin:0; font-size: 13px;"><b>M-Pesa Paybill:</b> 501101 | <b>Account:</b> 00001</p>
        </div>
        
        <button onclick="loadData()" class="btn" style="background:#0284c7; margin-bottom: 12px;">Refresh Data</button>
        <div id="users-table">Loading users...</div>

        <script>
            async function loadData() {
                const res = await fetch('/api/admin/users');
                const users = await res.json();
                let html = '<table><tr><th>TG ID</th><th>Name</th><th>Phone</th><th>Balance</th><th>PRO</th><th>Action</th></tr>';
                users.forEach(u => {
                    html += `<tr>
                        <td>${u.telegram_id}</td>
                        <td>${u.full_name || 'N/A'}</td>
                        <td>${u.phone_number || 'N/A'}</td>
                        <td>KES ${parseFloat(u.balance).toFixed(2)}</td>
                        <td><b style="color:${u.is_pro ? '#4ade80' : '#f87171'}">${u.is_pro ? 'PRO' : 'Free'}</b></td>
                        <td><button class="btn" onclick="togglePro(${u.telegram_id}, ${!u.is_pro})">${u.is_pro ? 'Downgrade' : 'Upgrade PRO'}</button></td>
                    </tr>`;
                });
                html += '</table>';
                document.getElementById('users-table').innerHTML = html;
            }

            async function togglePro(tgId, makePro) {
                await fetch('/api/admin/toggle-pro', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ telegram_id: tgId, is_pro: makePro })
                });
                loadData();
            }
            loadData();
        </script>
    </body>
    </html>
    '''

@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    users = execute_query("SELECT telegram_id, full_name, phone_number, balance, is_pro FROM users;", fetchall=True)
    return jsonify(users)

@app.route('/api/admin/toggle-pro', methods=['POST'])
def admin_toggle_pro():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    is_pro = 1 if data.get('is_pro') else 0
    execute_query("UPDATE users SET is_pro = %s WHERE telegram_id = %s;", (is_pro, tg_id), commit=True)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
