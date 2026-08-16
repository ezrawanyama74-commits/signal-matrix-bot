import os
from flask import Flask, render_template, send_from_file

app = Flask(__name__, template_folder='templates', static_folder='templates')

@app.route('/')
def home():
    if os.path.exists('templates/index.html'):
        return render_template('index.html')
    return "LipaViews Backend Active", 200

@app.route('/health')
def health():
    return {"status": "ok", "message": "LipaViews backend active"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
