import os
import time
import random
import psycopg2
from pyrogram import Client
from database import get_db
from config import API_ID, API_HASH

# Initialize Pyrogram Userbot Client
app = Client("outreach_userbot", api_id=API_ID, api_hash=API_HASH)

# Outreach Target Keywords & Pitch Messages
PITCH_TEMPLATES = [
    "Hey! Saw your post regarding channel growth. We offer real organic YouTube and Telegram views/traffic with instant delivery. Check out our bot @LipaViewsBot to place an order!",
    "Hi there! Need real views or channel engagement? LipaViews delivers high-retention traffic fast. Get started directly via @LipaViewsBot!",
    "Hello! If you're looking for fast, affordable views or channel boosting, try our system at @LipaViewsBot. Setup takes under a minute!"
]

def init_outreach_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outreach_log (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    cursor.close()
    conn.close()

def is_already_contacted(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM outreach_log WHERE user_id = %s;", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row is not None

def log_contacted_user(user_id, username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO outreach_log (user_id, username) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
        (user_id, username)
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_daily_count():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM outreach_log WHERE sent_at >= CURRENT_DATE;")
    res = cursor.fetchone()
    cursor.close()
    conn.close()
    return res['cnt'] if res else 0

def run_outreach():
    init_outreach_db()
    
    # Target public groups to find clients looking for views/traffic
    target_groups = ["@Tg_Promote_Group", "@Youtube_Sub_4_Sub", "@TelegramPromotions"]
    
    max_daily_dms = 15
    current_sent = get_daily_count()

    print(f"--- LipaViews Outreach Started ---")
    print(f"Sent today so far: {current_sent}/{max_daily_dms}")

    if current_sent >= max_daily_dms:
        print("Daily cap of 15 DMs already reached. Stopping outreach for today.")
        return

    with app:
        for group in target_groups:
            if current_sent >= max_daily_dms:
                break

            try:
                print(f"Checking target group: {group}")
                # Fetch recent members/messages
                for member in app.get_chat_members(group, limit=50):
                    if current_sent >= max_daily_dms:
                        print("Reached 15 DMs cap! Halting outreach run.")
                        break

                    user = member.user
                    if user.is_bot or user.is_deleted or is_already_contacted(user.id):
                        continue

                    # Select random pitch template
                    pitch = random.choice(PITCH_TEMPLATES)

                    try:
                        app.send_message(user.id, pitch)
                        log_contacted_user(user.id, user.username)
                        current_sent += 1
                        print(f"[{current_sent}/15] Sent outreach DM to @{user.username or user.id}")

                        # Random humanized delay between 20 to 40 minutes (1200 - 2400 seconds)
                        # Reduced delay for testing if needed, default is set to realistic human pace
                        delay = random.randint(1200, 2400)
                        print(f"Waiting {delay // 60} minutes before sending next message...")
                        time.sleep(delay)

                    except Exception as e:
                        print(f"Could not send DM to {user.id}: {e}")
                        time.sleep(10)

            except Exception as e:
                print(f"Error accessing group {group}: {e}")

if __name__ == '__main__':
    run_outreach()
