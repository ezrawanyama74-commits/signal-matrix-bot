import os
import sqlite3

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
        cur.execute("DROP TABLE IF EXISTS tasks;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone_number TEXT,
                balance REAL DEFAULT 0.00,
                pro_tier TEXT DEFAULT 'free',
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
                required_tier TEXT DEFAULT 'free'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                telegram_id INTEGER PRIMARY KEY,
                task_id INTEGER,
                watch_started_at REAL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                task_id INTEGER,
                completed_at REAL,
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
        cur.execute("""
            INSERT INTO tasks (title, video_url, reward_kes, duration_sec, required_tier) VALUES
            ('Watch LipaViews Free Task', 'https://www.youtube.com/embed/M7lc1UVf-VE', 2.00, 15, 'free'),
            ('Watch Sponsored Promo Video', 'https://www.youtube.com/embed/dQw4w9WgXcQ', 2.00, 15, 'free'),
            ('PRO 1 Task: High Yield Ad', 'https://www.youtube.com/embed/M7lc1UVf-VE', 10.00, 15, 'pro_1'),
            ('PRO 2 Task: Premium Partner Review', 'https://www.youtube.com/embed/M7lc1UVf-VE', 20.00, 15, 'pro_2');
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                full_name VARCHAR(255),
                phone_number VARCHAR(50),
                balance NUMERIC(10,2) DEFAULT 0.00,
                pro_tier VARCHAR(20) DEFAULT 'free',
                referral_code VARCHAR(100) UNIQUE,
                minipay_wallet VARCHAR(255)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                video_url TEXT NOT NULL,
                reward_kes NUMERIC(10,2) DEFAULT 2.00,
                duration_sec INT DEFAULT 15,
                required_tier VARCHAR(20) DEFAULT 'free'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                telegram_id BIGINT PRIMARY KEY,
                task_id INT,
                watch_started_at DOUBLE PRECISION
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT REFERENCES users(telegram_id),
                task_id INT REFERENCES tasks(id),
                completed_at DOUBLE PRECISION,
                CONSTRAINT unique_user_task UNIQUE (telegram_id, task_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                mpesa_receipt TEXT,
                amount NUMERIC(10,2),
                type VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending'
            );
        """)

    conn.commit()
    cur.close()
    conn.close()
