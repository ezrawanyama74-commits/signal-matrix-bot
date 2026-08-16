import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates', static_folder='templates')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

def init_db():
    if not DB_URL:
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        # 1. Users Table (Profile, Tiers, Streaks, Balance)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                username TEXT,
                balance NUMERIC(10,2) DEFAULT 0.00,
                is_vip BOOLEAN DEFAULT FALSE,
                referral_code TEXT UNIQUE,
                referred_by BIGINT,
                daily_completed_count INT DEFAULT 0,
                last_active_date DATE DEFAULT CURRENT_DATE
            );
        """)
        # 2. Watch Tasks Table (Validation, Pricing, Limits)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                video_url TEXT NOT NULL,
                reward_kes NUMERIC(10,2) DEFAULT 10.00,
                duration_sec INT DEFAULT 15,
                category VARCHAR(50) DEFAULT 'General',
                status VARCHAR(20) DEFAULT 'active'
            );
        """)
        # 3. User Task Completions (Anti-Cheat, Double-Claim Prevention)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT REFERENCES users(telegram_id),
                task_id INT REFERENCES tasks(id),
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_user_task UNIQUE (telegram_id, task_id)
            );
        """)
        # 4. M-Pesa Subscriptions & Deposits (VIP, Task Purchases)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                mpesa_receipt TEXT,
                amount NUMERIC(10,2),
                type VARCHAR(20), -- 'vip_upgrade', 'task_promotion', 'payout'
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Seed default tasks if empty
        cur.execute("SELECT COUNT(*) FROM tasks;")
        if cur.fetchone()['count'] == 0:
            cur.execute("""
                INSERT INTO tasks (title, video_url, reward_kes, duration_sec, category) VALUES
                ('Watch LipaViews Platform Intro', 'https://www.youtube.com/embed/M7lc1UVf-VE', 10.00, 15, 'Featured'),
                ('Learn Web3 & Telegram Mini Apps', 'https://www.youtube.com/embed/dQw4w9WgXcQ', 15.00, 15, 'Education');
            """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("DB Initialization Error:", e)

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# Feature 1-3: User Sync, Streaks, Referral Engine
@app.route('/api/sync-user', methods=['POST'])
def sync_user():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    username = data.get('username', 'Anonymous')
    referrer = data.get('referrer_id')

    if not tg_id:
        return jsonify({"error": "Invalid Telegram context"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (tg_id,))
    user = cur.fetchone()

    if not user:
        ref_code = f"ref_{tg_id}"
        cur.execute("""
            INSERT INTO users (telegram_id, username, referral_code, referred_by)
            VALUES (%s, %s, %s, %s) RETURNING *;
        """, (tg_id, username, ref_code, referrer if referrer != tg_id else None))
        user = cur.fetchone()
        conn.commit()

    cur.close()
    conn.close()
    return jsonify({"status": "success", "user": user})

# Feature 4-6: Dynamic Task Fetching & Category Filtering
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tg_id = request.args.get('telegram_id')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.*, 
               CASE WHEN tc.id IS NOT NULL THEN TRUE ELSE FALSE END AS completed
        FROM tasks t
        LEFT JOIN task_completions tc ON t.id = tc.task_id AND tc.telegram_id = %s
        WHERE t.status = 'active';
    """, (tg_id,))
    tasks = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({"tasks": tasks})

# Feature 7-9: Anti-Cheat Mandatory Watch Validation & Reward Claiming
@app.route('/api/claim-reward', methods=['POST'])
def claim_reward():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    task_id = data.get('task_id')
    watch_time = data.get('watch_time_sec', 0)

    if watch_time < 15:
        return jsonify({"error": "Anti-Cheat Triggered: Mandatory 15s watch time required"}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO task_completions (telegram_id, task_id) VALUES (%s, %s);", (tg_id, task_id))
        cur.execute("SELECT reward_kes FROM tasks WHERE id = %s;", (task_id,))
        task = cur.fetchone()
        reward = task['reward_kes'] if task else 10.00
        
        cur.execute("UPDATE users SET balance = balance + %s, daily_completed_count = daily_completed_count + 1 WHERE telegram_id = %s RETURNING balance;", (reward, tg_id))
        new_balance = cur.fetchone()['balance']
        conn.commit()
        return jsonify({"message": f"Claimed KES {reward}!", "new_balance": float(new_balance)})
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"error": "Task already completed"}), 400
    finally:
        cur.close()
        conn.close()

# Feature 10-12: M-Pesa VIP Subscriptions & Task Promotion Requests
@app.route('/api/deposit-request', methods=['POST'])
def deposit_request():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    receipt = data.get('mpesa_receipt')
    amount = data.get('amount')
    trans_type = data.get('type') # 'vip_upgrade' or 'task_promotion'

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (telegram_id, mpesa_receipt, amount, type)
        VALUES (%s, %s, %s, %s);
    """, (tg_id, receipt, amount, trans_type))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Transaction submitted for verification!"})

# Feature 13-15: Sunday Payout Requests & Referral Leaderboard
@app.route('/api/request-payout', methods=['POST'])
def request_payout():
    data = request.get_json() or {}
    tg_id = data.get('telegram_id')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance, is_vip FROM users WHERE telegram_id = %s;", (tg_id,))
    user = cur.fetchone()

    if not user or user['balance'] < 100.00:
        return jsonify({"error": "Minimum Sunday payout threshold is KES 100.00"}), 400

    cur.execute("UPDATE users SET balance = 0.00 WHERE telegram_id = %s;", (tg_id,))
    cur.execute("INSERT INTO transactions (telegram_id, amount, type, status) VALUES (%s, %s, 'payout', 'scheduled_sunday');", (tg_id, user['balance']))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Payout requested! Scheduled for batch release on Sunday."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
