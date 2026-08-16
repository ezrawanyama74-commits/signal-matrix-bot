import os

# Telegram Credentials
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "123456789"))

# Userbot Credentials (for 15 DMs/day outreach)
API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH_HERE")

# M-Pesa Info
PAYBILL_NUMBER = "501101"
ACCOUNT_NUMBER = "00001"

# Tier Reward Definitions
TIER_REWARDS = {
    "free": 2.0,      # 2 KSH / video
    "pro_1": 10.0,    # 10 KSH / video (100 KSH sub)
    "pro_2": 20.0     # 20 KSH / video (200 KSH sub)
}

MIN_WITHDRAWAL_KSH = 130.0  # ~$1.00
