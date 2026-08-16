import os
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///lipaviews.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    pro_tier = db.Column(db.String(20), default='free')
    videos_watched_today = db.Column(db.Integer, default=0)
    last_watch_date = db.Column(db.String(20), default='')

class VideoTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    video_url = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    reward_kes = db.Column(db.Float, default=2.0)
    max_views = db.Column(db.Integer, default=100)
    current_views = db.Column(db.Integer, default=0)

class ActiveWatchSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('video_task.id', ondelete='CASCADE'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserWatchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('video_task.id', ondelete='CASCADE'), nullable=False)

class WithdrawalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- PAGE ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# --- USER API ROUTES ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    phone = data.get('phone_number')
    full_name = data.get('full_name')

    if not phone or not full_name:
        return jsonify({'error': 'Name and phone number are required'}), 400

    user = User.query.filter_by(phone_number=phone).first()
    if not user:
        user = User(
            telegram_id=phone,
            full_name=full_name,
            phone_number=phone,
            balance=0.0,
            pro_tier='free'
        )
        db.session.add(user)
        db.session.commit()
    else:
        user.full_name = full_name
        db.session.commit()

    return jsonify({
        'status': 'success',
        'user': {
            'id': user.id,
            'phone_number': user.phone_number,
            'full_name': user.full_name,
            'balance': user.balance,
            'pro_tier': user.pro_tier,
            'videos_watched_today': user.videos_watched_today
        }
    })

@app.route('/api/user-data')
def get_user_data():
    phone = request.args.get('phone_number')
    user = User.query.filter_by(phone_number=phone).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    today_str = str(date.today())
    if user.last_watch_date != today_str:
        user.videos_watched_today = 0
        user.last_watch_date = today_str
        db.session.commit()

    return jsonify({
        'id': user.id,
        'full_name': user.full_name,
        'phone_number': user.phone_number,
        'balance': user.balance,
        'pro_tier': user.pro_tier,
        'videos_watched_today': user.videos_watched_today
    })

@app.route('/api/next-task')
def next_task():
    phone = request.args.get('phone_number')
    user = User.query.filter_by(phone_number=phone).first()
    if not user:
        return jsonify({'error': 'User missing'}), 404

    today_str = str(date.today())
    if user.last_watch_date != today_str:
        user.videos_watched_today = 0
        user.last_watch_date = today_str
        db.session.commit()

    limits = {'free': 10, 'pro1': 100, 'pro2': 999999}
    max_allowed = limits.get(user.pro_tier, 10)

    if user.videos_watched_today >= max_allowed:
        return jsonify({
            'limit_reached': True,
            'message': f'Daily limit reached ({max_allowed} videos/day for {user.pro_tier.upper()} tier).'
        })

    watched_ids = [h.task_id for h in UserWatchHistory.query.filter_by(user_id=user.id).all()]
    task = VideoTask.query.filter(
        ~VideoTask.id.in_(watched_ids),
        VideoTask.current_views < VideoTask.max_views
    ).first()

    if not task:
        return jsonify({'task': None, 'message': 'No more video tasks available today.'})

    ActiveWatchSession.query.filter_by(user_id=user.id).delete()
    session = ActiveWatchSession(user_id=user.id, task_id=task.id, started_at=datetime.utcnow())
    db.session.add(session)
    db.session.commit()

    tier_rewards = {'free': 2.0, 'pro1': 10.0, 'pro2': 20.0}
    reward = tier_rewards.get(user.pro_tier, 2.0)

    return jsonify({
        'task': {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'video_url': task.video_url,
            'reward_kes': reward
        }
    })

@app.route('/api/claim-reward', methods=['POST'])
def claim_reward():
    data = request.json
    phone = data.get('phone_number')
    task_id = data.get('task_id')

    user = User.query.filter_by(phone_number=phone).first()
    task = VideoTask.query.get(task_id)

    if not user or not task:
        return jsonify({'error': 'Invalid request parameters'}), 400

    active_session = ActiveWatchSession.query.filter_by(user_id=user.id, task_id=task.id).first()
    if not active_session:
        return jsonify({'error': 'No active watch session found for this task.'}), 400

    elapsed_seconds = (datetime.utcnow() - active_session.started_at).total_seconds()
    if elapsed_seconds < 20.0:
        return jsonify({'error': f'Must watch for at least 20 seconds. (Elapsed: {int(elapsed_seconds)}s)'}), 400

    limits = {'free': 10, 'pro1': 100, 'pro2': 999999}
    if user.videos_watched_today >= limits.get(user.pro_tier, 10):
        return jsonify({'error': 'Daily limit reached for your current tier.'}), 400

    db.session.delete(active_session)
    history = UserWatchHistory(user_id=user.id, task_id=task.id)
    task.current_views += 1
    
    tier_rewards = {'free': 2.0, 'pro1': 10.0, 'pro2': 20.0}
    reward = tier_rewards.get(user.pro_tier, 2.0)

    user.balance += reward
    user.videos_watched_today += 1
    user.last_watch_date = str(date.today())

    db.session.add(history)
    db.session.commit()

    return jsonify({
        'message': f'Successfully earned KES {reward:.2f}!',
        'new_balance': user.balance,
        'watched_today': user.videos_watched_today
    })

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    phone = data.get('phone_number')

    user = User.query.filter_by(phone_number=phone).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.balance < 130.0:
        return jsonify({'error': 'Minimum withdrawal limit is KES 130.00.'}), 400

    amount_to_withdraw = user.balance
    user.balance = 0.0

    req = WithdrawalRequest(
        user_id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        amount=amount_to_withdraw
    )
    db.session.add(req)
    db.session.commit()

    return jsonify({'message': f'Withdrawal request of KES {amount_to_withdraw:.2f} submitted successfully!'})

# --- ADMIN API ROUTES ---

@app.route('/api/admin/data')
def admin_data():
    try:
        users = User.query.all()
        tasks = VideoTask.query.all()
        withdrawals = WithdrawalRequest.query.all()

        user_list = [{
            'id': u.id,
            'full_name': u.full_name,
            'phone_number': u.phone_number,
            'balance': u.balance,
            'pro_tier': u.pro_tier,
            'videos_watched_today': u.videos_watched_today
        } for u in users]

        task_list = [{
            'id': t.id,
            'title': t.title,
            'video_url': t.video_url,
            'description': t.description,
            'max_views': t.max_views,
            'current_views': t.current_views
        } for t in tasks]

        payout_list = [{
            'id': w.id,
            'full_name': w.full_name,
            'phone_number': w.phone_number,
            'amount': w.amount,
            'status': w.status
        } for w in withdrawals]

        return jsonify({'users': user_list, 'tasks': task_list, 'withdrawals': payout_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/add-video', methods=['POST'])
def add_video():
    data = request.json
    task = VideoTask(
        title=data.get('title'),
        video_url=data.get('video_url'),
        description=data.get('description', ''),
        max_views=int(data.get('max_views', 100)),
        reward_kes=2.0
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({'message': 'Video task added successfully!'})

@app.route('/api/admin/update-tier', methods=['POST'])
def update_tier():
    data = request.json
    user = User.query.get(data.get('user_id'))
    if user:
        user.pro_tier = data.get('pro_tier')
        db.session.commit()
        return jsonify({'message': 'Tier updated successfully!'})
    return jsonify({'error': 'User not found'}), 404

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
