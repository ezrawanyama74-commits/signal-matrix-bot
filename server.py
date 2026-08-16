import os
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from database import get_db
from config import TIER_REWARDS, MIN_WITHDRAWAL_KSH

app = Flask(__name__)

# 1. Register User (Full Name + Phone Number)
@app.route('/api/auth/register', methods=['POST'])
def register_user():
    data = request.json or {}
    user_id = data.get('user_id')
    full_name = data.get('full_name')
    phone_number = data.get('phone_number')

    if not user_id or not full_name or not phone_number:
        return jsonify({"status": "error", "message": "User ID, Full Name, and Phone are required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, full_name, phone_number) VALUES (%s, %s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET full_name = EXCLUDED.full_name, phone_number = EXCLUDED.phone_number;",
        (user_id, full_name, phone_number)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": "Registration complete!"})

# 2. Get User Profile & Wallet Info
@app.route('/api/user/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name, phone_number, wallet_balance, tier FROM users WHERE user_id = %s;", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "User not found."}), 404

    return jsonify({"status": "success", "user": user})

# 3. Get Active Single Video (Sequential Queue)
@app.route('/api/video/current', methods=['GET'])
def get_current_video():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()

    # Get user tier
    cursor.execute("SELECT tier FROM users WHERE user_id = %s;", (user_id,))
    user = cursor.fetchone()
    user_tier = user['tier'] if user else 'free'

    # Check for active assigned video
    cursor.execute(
        "SELECT p.id as progress_id, v.id as video_id, v.video_url, v.title, v.min_watch_seconds "
        "FROM user_video_progress p JOIN videos v ON p.video_id = v.id "
        "WHERE p.user_id = %s AND p.status = 'assigned' LIMIT 1;", (user_id,)
    )
    progress = cursor.fetchone()

    if not progress:
        # Assign next uncompleted video matching user tier or lower
        cursor.execute(
            "SELECT * FROM videos WHERE is_active = TRUE AND current_views < target_view_limit "
            "AND tier = %s AND id NOT IN ("
            "  SELECT video_id FROM user_video_progress WHERE user_id = %s AND status = 'completed'"
            ") ORDER BY id ASC LIMIT 1;", (user_tier, user_id)
        )
        next_video = cursor.fetchone()

        if not next_video:
            cursor.close()
            conn.close()
            return jsonify({"status": "empty", "message": "No new videos available in your tier."})

        # Assign video
        cursor.execute(
            "INSERT INTO user_video_progress (user_id, video_id, status) VALUES (%s, %s, 'assigned') RETURNING id;",
            (user_id, next_video['id'])
        )
        conn.commit()
        
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "video_id": next_video['id'],
            "title": next_video['title'],
            "video_url": next_video['video_url'],
            "min_watch_seconds": next_video['min_watch_seconds']
        })

    cursor.close()
    conn.close()
    return jsonify({
        "status": "success",
        "video_id": progress['video_id'],
        "title": progress['title'],
        "video_url": progress['video_url'],
        "min_watch_seconds": progress['min_watch_seconds']
    })

# 4. Verify Watch Timer & Add Reward
@app.route('/api/video/verify', methods=['POST'])
def verify_video():
    data = request.json or {}
    user_id = data.get('user_id')
    video_id = data.get('video_id')
    comment = data.get('comment', '').strip()

    if not comment or len(comment) < 3:
        return jsonify({"status": "error", "message": "Please write a valid comment."}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT p.*, v.min_watch_seconds FROM user_video_progress p "
        "JOIN videos v ON p.video_id = v.id WHERE p.user_id = %s AND p.video_id = %s AND p.status = 'assigned';",
        (user_id, video_id)
    )
    progress = cursor.fetchone()

    if not progress:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "No active session found."}), 400

    # Calculate server-side watch duration
    assigned_at = progress['assigned_at']
    elapsed = (datetime.now() - assigned_at).total_seconds()

    if elapsed < progress['min_watch_seconds']:
        cursor.close()
        conn.close()
        return jsonify({
            "status": "error",
            "message": f"Must watch for at least {progress['min_watch_seconds']} seconds. Only {int(elapsed)}s passed."
        }), 400

    # Get user reward tier
    cursor.execute("SELECT tier FROM users WHERE user_id = %s;", (user_id,))
    user = cursor.fetchone()
    reward = TIER_REWARDS.get(user['tier'], 2.0)

    # Atomic Update
    cursor.execute(
        "UPDATE user_video_progress SET status = 'completed', completed_at = CURRENT_TIMESTAMP, comment_text = %s WHERE id = %s;",
        (comment, progress['id'])
    )
    cursor.execute("UPDATE videos SET current_views = current_views + 1 WHERE id = %s;", (video_id,))
    cursor.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE user_id = %s;", (reward, user_id))
    
    # Auto-disable video if target view limit reached
    cursor.execute("UPDATE videos SET is_active = FALSE WHERE id = %s AND current_views >= target_view_limit;", (video_id,))
    conn.commit()

    # Get updated balance
    cursor.execute("SELECT wallet_balance FROM users WHERE user_id = %s;", (user_id,))
    new_balance = cursor.fetchone()['wallet_balance']

    cursor.close()
    conn.close()

    return jsonify({
        "status": "success",
        "message": f"+{reward} KSH added!",
        "new_balance": new_balance
    })

# 5. Submit M-Pesa Subscription Message
@app.route('/api/subscription/submit', methods=['POST'])
def submit_subscription():
    data = request.json or {}
    user_id = data.get('user_id')
    mpesa_message = data.get('mpesa_message', '').strip()

    if not mpesa_message:
        return jsonify({"status": "error", "message": "M-Pesa message required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO subscriptions (user_id, mpesa_message, status) VALUES (%s, %s, 'pending');",
        (user_id, mpesa_message)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": "Subscription pending admin approval."})

# 6. Request Withdrawal (130 KSH Minimum)
@app.route('/api/wallet/withdraw', methods=['POST'])
def request_withdrawal():
    data = request.json or {}
    user_id = data.get('user_id')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT wallet_balance FROM users WHERE user_id = %s;", (user_id,))
    user = cursor.fetchone()

    if not user or user['wallet_balance'] < MIN_WITHDRAWAL_KSH:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": f"Minimum withdrawal is {MIN_WITHDRAWAL_KSH} KSH."}), 400

    amount = user['wallet_balance']
    cursor.execute("INSERT INTO payouts (user_id, amount, status) VALUES (%s, %s, 'pending');", (user_id, amount))
    cursor.execute("UPDATE users SET wallet_balance = 0.0 WHERE user_id = %s;", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": "Withdrawal requested! Payouts process every Sunday."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
