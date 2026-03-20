import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, g, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai

# --- CONFIG ---
app = Flask(__name__)
app.secret_key = secrets.token_hex(64)
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

DB_PATH = "absolute_zero.db"
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = 30 # Minutes

# --- DATABASE ---
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        # Security Columns: failed_attempts (INT), lockout_until (DATETIME)
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, 
            name TEXT UNIQUE, 
            pwd TEXT, 
            failed_attempts INTEGER DEFAULT 0, 
            lockout_until DATETIME)''')
        db.execute('CREATE TABLE IF NOT EXISTS archive (id INTEGER PRIMARY KEY, owner TEXT, role TEXT, msg TEXT)')
        db.commit()

# --- SECURITY GATE ---
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    name = data.get('name')
    pwd = data.get('password')
    db = get_db()
    
    user = db.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    # 1. Check Lockout Status
    now = datetime.now()
    if user['lockout_until']:
        lockout_time = datetime.fromisoformat(user['lockout_until'])
        if now < lockout_time:
            wait_min = int((lockout_time - now).total_seconds() / 60)
            return jsonify({"error": f"Account locked. Try again in {wait_min} minutes."}), 403

    # 2. Verify Password
    if check_password_hash(user['pwd'], pwd):
        # SUCCESS: Reset Shield
        db.execute("UPDATE users SET failed_attempts = 0, lockout_until = NULL WHERE name = ?", (name,))
        db.commit()
        session.clear()
        session['user_id'] = user['name']
        return jsonify({"success": True})
    else:
        # FAILURE: Increment Attempts
        new_attempts = user['failed_attempts'] + 1
        lockout_ts = None
        if new_attempts >= MAX_ATTEMPTS:
            lockout_ts = (now + timedelta(minutes=LOCKOUT_DURATION)).isoformat()
            msg = f"Too many attempts. Locked for {LOCKOUT_DURATION}m."
        else:
            msg = f"Invalid credentials. {MAX_ATTEMPTS - new_attempts} attempts left."
        
        db.execute("UPDATE users SET failed_attempts = ?, lockout_until = ? WHERE name = ?", 
                   (new_attempts, lockout_ts, name))
        db.commit()
        return jsonify({"error": msg}), 401

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name, pwd = data.get('name', '').strip(), data.get('password', '')
    if not name or len(pwd) < 12:
        return jsonify({"error": "Username required & Password 12+ chars"}), 400
    
    db = get_db()
    try:
        h = generate_password_hash(pwd)
        db.execute("INSERT INTO users (name, pwd) VALUES (?, ?)", (name, h))
        db.commit()
        return jsonify({"success": "Identity Saved"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Identity already exists"}), 400

@app.route("/ask", methods=["POST"])
def ask():
    if 'user_id' not in session: abort(401)
    user_msg = request.json.get("message")
    db = get_db()
    
    # Gemini Context Processing
    rows = db.execute("SELECT role, msg FROM archive WHERE owner=? ORDER BY id DESC LIMIT 5", (session['user_id'],)).fetchall()
    history = [{"role": "user" if r['role'] == "user" else "model", "parts": [r['msg']]} for r in reversed(rows)]

    model = genai.GenerativeModel('gemini-1.5-flash')
    chat = model.start_chat(history=history)
    response = chat.send_message(user_msg)
    
    db.execute("INSERT INTO archive (owner, role, msg) VALUES (?, 'user', ?)", (session['user_id'], user_msg))
    db.execute("INSERT INTO archive (owner, role, msg) VALUES (?, 'ai', ?)", (session['user_id'], response.text))
    db.commit()

    return jsonify({"answer": response.text})

@app.route("/")
def index():
    return render_template_string(TITANIUM_UI)

# --- (UI HTML stays mostly same, but update script for better error alerts) ---
TITANIUM_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Randy-X | Absolute Zero</title>
    <style>
        body { background: #000; color: #0f0; font-family: 'Consolas', monospace; }
        .gate { position: fixed; inset: 0; background: #000; display: flex; align-items: center; justify-content: center; z-index: 100; }
        .card { border: 1px solid #0f0; padding: 30px; background: #050505; width: 300px; }
        input { width: 100%; background: #000; border: 1px solid #050; color: #0f0; padding: 10px; margin: 10px 0; box-sizing: border-box; }
        .btn { background: #0f0; color: #000; border: none; padding: 10px; width: 100%; cursor: pointer; font-weight: bold; }
        #chat { height: 80vh; overflow-y: auto; padding: 20px; border-bottom: 1px solid #030; }
        .ai { color: #0f0; margin: 10px 0; }
        .user { color: #fff; text-align: right; margin: 10px 0; opacity: 0.7; }
    </style>
</head>
<body>
    <div id="login-gate" class="gate">
        <div class="card">
            <h2 style="text-align:center">SECURE LINK</h2>
            <input type="text" id="u" placeholder="USER_ID">
            <input type="password" id="p" placeholder="PASS_KEY">
            <button class="btn" onclick="auth('login')">INITIALIZE</button>
            <button onclick="auth('register')" style="background:none; border:none; color:#050; width:100%; margin-top:10px; cursor:pointer;">New Identity</button>
        </div>
    </div>
    <div id="chat"></div>
    <div style="display:flex; padding:10px;">
        <input type="text" id="msg" style="flex:1" placeholder="Enter Command..." onkeypress="if(event.key=='Enter')send()">
        <button class="btn" style="width:100px; margin-left:10px;" onclick="send()">RUN</button>
    </div>
    <script>
        async function auth(m) {
            const r = await fetch('/'+m, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:u.value, password:p.value})});
            const d = await r.json();
            if(d.success) {
                if(m==='register') alert("Identity Saved.");
                else document.getElementById('login-gate').style.display='none';
            } else alert(d.error);
        }
        async function send() {
            const v = msg.value; if(!v) return;
            append(v, 'user'); msg.value = '';
            const r = await fetch('/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:v})});
            const d = await r.json();
            append(d.answer || d.error, 'ai');
        }
        function append(t, r) {
            const div = document.createElement('div');
            div.className = r;
            div.innerText = (r === 'ai' ? 'GEMINI > ' : 'YOU > ') + t;
            const chat = document.getElementById('chat');
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=5000)
