import os

def setup():
    print("=== LipaViews Environment Setup ===")
    print("Enter your credentials below. They will be saved to a local .env file.")
    print("---------------------------------------------------------------------")

    bot_token = input("Enter your Telegram Bot Token: ").strip()
    admin_id = input("Enter your Admin Telegram User ID: ").strip()
    api_id = input("Enter your Telethon/Pyrogram API ID: ").strip()
    api_hash = input("Enter your Telethon/Pyrogram API HASH: ").strip()
    db_url = input("Enter PostgreSQL DATABASE_URL (or press Enter for default local DB): ").strip()

    if not db_url:
        db_url = "postgresql://postgres:password@localhost:5432/lipaviews_db"

    env_content = f"""DATABASE_URL={db_url}
BOT_TOKEN={bot_token}
ADMIN_TELEGRAM_ID={admin_id}
API_ID={api_id}
API_HASH={api_hash}
"""

    with open(".env", "w") as f:
        f.write(env_content)

    print("\n[SUCCESS] .env file created successfully! Your credentials are now safely stored locally.")

if __name__ == "__main__":
    setup()
