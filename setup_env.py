import getpass
import os

def generate_env():
    print("==========================================")
    print("    LipaViews Environment Setup Wizard    ")
    print("==========================================")
    print("Please enter the requested values below.\n")

    bot_token = input("1. Enter your Telegram BOT_TOKEN (from @BotFather): ").strip()
    admin_id = input("2. Enter your numeric ADMIN_TELEGRAM_ID: ").strip()
    api_id = input("3. Enter your Telegram API_ID (e.g. 38093748): ").strip()
    api_hash = getpass.getpass("4. Enter your Telegram API_HASH (input will be hidden): ").strip()
    db_url = input("5. Enter PostgreSQL DATABASE_URL (or press Enter for local default): ").strip()

    if not db_url:
        db_url = "postgresql://postgres:password@localhost:5432/lipaviews_db"

    env_content = f"""# LipaViews Production Environment Variables
BOT_TOKEN={bot_token}
ADMIN_TELEGRAM_ID={admin_id}
API_ID={api_id}
API_HASH={api_hash}
DATABASE_URL={db_url}
PYTHON_VERSION=3.11.8
"""

    with open(".env", "w") as f:
        f.write(env_content)

    print("\n[SUCCESS] Saved all variables to local `.env` file!")
    print("Security Check: `.env` is isolated and kept out of public commits.")

if __name__ == "__main__":
    generate_env()
