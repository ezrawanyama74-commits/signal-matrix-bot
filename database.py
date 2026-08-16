import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/bot_db")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            wallet_balance DOUBLE PRECISION DEFAULT 0.0,
            tier TEXT DEFAULT 'free', -- 'free', 'pro_1', 'pro_2'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # 2. Videos Table (with view limits)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id SERIAL PRIMARY KEY,
            video_url TEXT NOT NULL,
            title TEXT NOT NULL,
            tier TEXT DEFAULT 'free', -- 'free', 'pro_1', 'pro_2'
            target_view_limit INT NOT NULL,
            current_views INT DEFAULT 0,
            min_watch_seconds INT DEFAULT 15,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # 3. User Video Watch History & Timer Anti-Cheat
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_video_progress (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            video_id INT REFERENCES videos(id),
            status TEXT DEFAULT 'assigned', -- 'assigned', 'completed'
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            comment_text TEXT,
            UNIQUE(user_id, video_id)
        );
    ''')

    # 4. Pending Subscriptions (M-Pesa Verification)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            mpesa_message TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # 5. Weekly Payouts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payouts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            amount DOUBLE PRECISION NOT NULL,
            status TEXT DEFAULT 'pending', -- 'pending', 'paid'
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP
        );
    ''')

    conn.commit()
    cursor.close()
    conn.close()
    print("PostgreSQL Database Schema Initialized Successfully!")

if __name__ == "__main__":
    init_db()
