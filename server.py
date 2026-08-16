import os
import psycopg2
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates', static_folder='templates')

DB_URL = os.environ.get('DATABASE_URL')

def init_db():
    if not DB_URL:
        return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS video_tasks (
                id SERIAL PRIMARY KEY,
                video_url TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/submit-task', methods=['POST'])
def submit_task():
    data = request.get_json() or {}
    video_url = data.get('video_url')
    
    if not video_url:
        return jsonify({"error": "Video URL required"}), 400

    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("INSERT INTO video_tasks (video_url) VALUES (%s)", (video_url,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Task submitted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
