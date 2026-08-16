import sqlite3

def init_db():
    conn = sqlite3.connect('bot_business.db', timeout=30.0)
    cursor = conn.cursor()
    
    # Enforce WAL mode to process parallel reads/writes smoothly on mobile storage
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # Users table: Keeps track of point metrics, time tracking parameters, and registration data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            phone_number TEXT,
            active_video_id INTEGER DEFAULT NULL,
            click_timestamp REAL DEFAULT 0.0
        )
    ''')
    
    # Video tasks table: Manages tracking urls and caps out target metrics immediately
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_tasks (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            max_views INTEGER,
            current_views INTEGER DEFAULT 0,
            payout_rate REAL DEFAULT 2.0,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # View logs: Strict anti-cheat matching architecture
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS view_logs (
            user_id INTEGER,
            video_id INTEGER,
            PRIMARY KEY (user_id, video_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ System Core Database successfully configured with WAL transaction safety!")

if __name__ == '__main__':
    init_db()
