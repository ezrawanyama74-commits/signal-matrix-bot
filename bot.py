import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_db
from config import BOT_TOKEN, ADMIN_TELEGRAM_ID

bot = telebot.TeleBot(BOT_TOKEN)

def is_admin(user_id):
    return int(user_id) == int(ADMIN_TELEGRAM_ID)

# 1. Start Command
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Welcome to LipaViews Bot! Launch the Mini App from the menu button to start earning.")
        return

    admin_menu = (
        "👑 **LipaViews Admin Dashboard**\n\n"
        "Commands:\n"
        "• /weekly_payouts - View Sunday pending payouts\n"
        "• /subscriptions - Review pending M-Pesa sub payments\n"
        "• /add_video - Add a new video campaign\n"
    )
    bot.reply_to(message, admin_menu, parse_mode="Markdown")

# 2. Add Video Link Command
# Format: /add_video url | target_views | tier (free/pro_1/pro_2) | title
@bot.message_handler(commands=['add_video'])
def add_video_cmd(message):
    if not is_admin(message.from_user.id):
        return

    try:
        parts = message.text.replace('/add_video', '').strip().split('|')
        if len(parts) < 4:
            bot.reply_to(message, "Usage: `/add_video URL | ViewsLimit | Tier | Title`\nExample: `/add_video https://youtu.be/xyz | 500 | free | Sample Video`", parse_mode="Markdown")
            return

        video_url = parts[0].strip()
        target_views = int(parts[1].strip())
        tier = parts[2].strip().lower()
        title = parts[3].strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO videos (video_url, title, tier, target_view_limit, min_watch_seconds) "
            "VALUES (%s, %s, %s, %s, 15);",
            (video_url, title, tier, target_views)
        )
        conn.commit()
        cursor.close()
        conn.close()

        bot.reply_to(message, f"✅ Video added successfully!\n\n📌 Title: {title}\n🎯 View Limit: {target_views}\n💎 Tier: {tier.upper()}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error adding video: {str(e)}")

# 3. Pending Subscriptions Review
@bot.message_handler(commands=['subscriptions'])
def view_subscriptions(message):
    if not is_admin(message.from_user.id):
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT s.id, s.user_id, s.mpesa_message, u.full_name, u.phone_number "
        "FROM subscriptions s JOIN users u ON s.user_id = u.user_id "
        "WHERE s.status = 'pending' ORDER BY s.id ASC LIMIT 5;"
    )
    subs = cursor.fetchall()
    cursor.close()
    conn.close()

    if not subs:
        bot.reply_to(message, "🎉 No pending subscriptions to approve!")
        return

    for s in subs:
        text = (
            f"💳 **Pending Subscription #{s['id']}**\n"
            f"👤 **Name:** {s['full_name']}\n"
            f"📱 **Phone:** {s['phone_number']}\n"
            f"💬 **SMS:**\n`{s['mpesa_message']}`"
        )
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("Approve Pro 1 (100 KSH)", callback_data=f"sub_approve_{s['id']}_pro_1"),
            InlineKeyboardButton("Approve Pro 2 (200 KSH)", callback_data=f"sub_approve_{s['id']}_pro_2")
        )
        markup.row(InlineKeyboardButton("❌ Reject", callback_data=f"sub_reject_{s['id']}"))
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# 4. Weekly Payouts List (Sunday Batch)
@bot.message_handler(commands=['weekly_payouts'])
def weekly_payouts(message):
    if not is_admin(message.from_user.id):
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT p.id as payout_id, p.amount, u.user_id, u.full_name, u.phone_number, u.tier, "
        "COUNT(uvp.id) as total_watched, "
        "AVG(EXTRACT(EPOCH FROM (uvp.completed_at - uvp.assigned_at))) as avg_time "
        "FROM payouts p "
        "JOIN users u ON p.user_id = u.user_id "
        "LEFT JOIN user_video_progress uvp ON u.user_id = uvp.user_id AND uvp.status = 'completed' "
        "WHERE p.status = 'pending' "
        "GROUP BY p.id, p.amount, u.user_id, u.full_name, u.phone_number, u.tier "
        "ORDER BY p.id ASC LIMIT 10;"
    )
    payouts = cursor.fetchall()
    cursor.close()
    conn.close()

    if not payouts:
        bot.reply_to(message, "🎉 No pending payouts right now!")
        return

    for p in payouts:
        avg_sec = round(p['avg_time'], 1) if p['avg_time'] else 0.0
        text = (
            f"📊 **SUNDAY PAYOUT REQUEST #{p['payout_id']}**\n"
            f"👤 **Name:** {p['full_name']}\n"
            f"📱 **Phone:** {p['phone_number']}\n"
            f"💎 **Tier:** {p['tier'].upper()}\n"
            f"🎬 **Videos Watched:** {p['total_watched']}\n"
            f"⏱️ **Avg Watch Time:** {avg_sec}s\n"
            f"💰 **Amount Owed:** {p['amount']} KSH"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Mark Paid via MiniPay", callback_data=f"pay_done_{p['payout_id']}"))
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# 5. Callback Query Handler (Inline Buttons)
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if not is_admin(call.from_user.id):
        return

    conn = get_db()
    cursor = conn.cursor()

    if call.data.startswith("sub_approve_"):
        # Format: sub_approve_ID_TIER
        _, _, sub_id, tier, level = call.data.split("_")
        assigned_tier = f"{tier}_{level}"

        cursor.execute("SELECT user_id FROM subscriptions WHERE id = %s;", (sub_id,))
        sub = cursor.fetchone()
        if sub:
            cursor.execute("UPDATE users SET tier = %s WHERE user_id = %s;", (assigned_tier, sub['user_id']))
            cursor.execute("UPDATE subscriptions SET status = 'approved' WHERE id = %s;", (sub_id,))
            conn.commit()
            bot.answer_callback_query(call.id, f"Approved! User is now {assigned_tier.upper()}")
            bot.edit_message_text(f"✅ Subscription #{sub_id} Approved as {assigned_tier.upper()}", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("sub_reject_"):
        sub_id = call.data.split("_")[2]
        cursor.execute("UPDATE subscriptions SET status = 'rejected' WHERE id = %s;", (sub_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "Rejected")
        bot.edit_message_text(f"❌ Subscription #{sub_id} Rejected", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("pay_done_"):
        payout_id = call.data.split("_")[2]
        cursor.execute("UPDATE payouts SET status = 'paid', paid_at = CURRENT_TIMESTAMP WHERE id = %s;", (payout_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "Payment Marked as Done!")
        bot.edit_message_text(f"✅ Payout #{payout_id} marked as PAID. User web account reset to 0 KSH.", call.message.chat.id, call.message.message_id)

    cursor.close()
    conn.close()

if __name__ == '__main__':
    print("LipaViews Admin Bot Started...")
    bot.infinity_polling()
