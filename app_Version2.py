import os
import sqlite3
import secrets
import re
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template_string, g
from flask_cors import CORS
from deep_translator import GoogleTranslator
from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. CONFIGURATION ---
# Replace with your actual key or set it in your Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = secrets.token_hex(64)
CORS(app)

DB_FILE = "randyx_pro_final.db"

# --- 2. DATABASE LOGIC ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_FILE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS users 
                     (id INTEGER PRIMARY KEY, name TEXT UNIQUE, password TEXT, 
                      hint TEXT, language TEXT DEFAULT 'en')''')
        db.commit()

init_db()

# --- 3. MATH & AI ENGINES ---
def safe_math(text):
    clean = re.sub(r'[^0-9\+\-\*\/\%\.\(\)]', '', text)
    if any(op in text for op in "+-*/%") and len(clean) > 1:
        try:
            return f"Result: {eval(clean, {'__builtins__': None}, {})}"
        except: return None
    return None

def get_ai_response(prompt, user_name):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        persona = f"You are Randy-X Pro, the elite AI assistant for {user_name}. Expertise: Python, Apps."
        response = model.generate_content([persona, prompt])
        return response.text
    except:
        return "Neural Link Offline. Check API Key."

# --- 4. BACKEND ROUTES ---
@app.route("/")
def home():
    return render_template_string(HTML_UI)

@app.route("/auth", methods=["POST"])
def auth():
    data = request.json
    name, password, mode = data.get('name'), data.get('password'), data.get('mode')
    db = get_db(); c = db.cursor()
    user = c.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()

    if mode == 'register':
        if user: return jsonify({"error": "User Exists"}), 400
        c.execute("INSERT INTO users (name, password, hint) VALUES (?, ?, ?)", 
                  (name, generate_password_hash(password), data.get('hint')))
        db.commit()
        return jsonify({"success": True})
    
    if user and check_password_hash(user['password'], password):
        return jsonify({"name": user['name']})
    return jsonify({"error": "Failed"}), 401

@app.route("/ask", methods=["POST"])
def ask():
    msg = request.form.get("message", "")
    user = request.form.get("username", "Admin")
    
    # Check Math -> Then AI
    res = safe_math(msg) or get_ai_response(msg, user)
    return jsonify({"answer": res})

# --- 5. THE MOBILE-PRO UI (HTML/CSS/JS) ---
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Randy-X Pro</title>
    <style>
        :root { --accent: #00d2ff; --bg: #050a15; --glass: rgba(255, 255, 255, 0.08); }
        body { margin: 0; font-family: sans-serif; background: var(--bg); color: white; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
        #auth { position: fixed; inset: 0; background: #000; z-index: 2000; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 15px; }
        header { padding: 15px 20px; background: rgba(0,0,0,0.5); backdrop-filter: blur(10px); border-bottom: 1px solid var(--glass); display: flex; justify-content: space-between; align-items: center; }
        #chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
        .msg { max-width: 85%; padding: 12px 18px; border-radius: 20px; font-size: 15px; line-height: 1.4; }
        .user { align-self: flex-end; background: var(--accent); color: #000; font-weight: bold; border-bottom-right-radius: 4px; }
        .ai { align-self: flex-start; background: var(--glass); border-bottom-left-radius: 4px; border: 1px solid rgba(255,255,255,0.1); }
        .dock { padding: 15px; background: rgba(0,0,0,0.7); display: flex; gap: 10px; padding-bottom: calc(15px + env(safe-area-inset-bottom)); }
        input { flex: 1; background: #111; border: 1px solid #333; color: white; padding: 12px 20px; border-radius: 25px; outline: none; font-size: 16px; }
        button { background: var(--accent); border: none; padding: 12px 20px; border-radius: 25px; font-weight: bold; cursor: pointer; }
        .fab { position: fixed; bottom: 100px; right: 20px; width: 50px; height: 50px; background: #111; border: 1px solid var(--accent); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 0 15px var(--accent); }
    </style>
</head>
<body>
    <div id="auth">
        <h2 style="color:var(--accent); letter-spacing:4px;">RANDY-X PRO</h2>
        <input type="text" id="un" placeholder="Username" style="flex:none; width:70%;">
        <input type="password" id="pw" placeholder="Password" style="flex:none; width:70%;">
        <button onclick="doAuth()" style="width:75%;">ACCESS SYSTEM</button>
    </div>
    <header>
        <span style="color:var(--accent); font-weight:bold;">RANDY-X CORE</span>
        <button onclick="localStorage.clear(); location.reload();" style="background:none; border:1px solid red; color:red; padding:5px 10px;">LOGOUT</button>
    </header>
    <div id="chat"></div>
    <div class="dock">
        <input type="text" id="mi" placeholder="Message Randy-X...">
        <button onclick="send()">SEND</button>
    </div>
    <div class="fab" onclick="alert('Calculator Integrated')">🖩</div>
    <script>
        if(localStorage.getItem('rx_u')) document.getElementById('auth').style.display='none';
        async function doAuth() {
            const name = document.getElementById('un').value;
            const password = document.getElementById('pw').value;
            const r = await fetch('/auth', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, password, mode:'login'})});
            const d = await r.json();
            if(d.name) { localStorage.setItem('rx_u', d.name); location.reload(); } else alert("Access Denied");
        }
        async function send() {
            const i = document.getElementById('mi'); if(!i.value) return;
            const b = document.getElementById('chat');
            b.innerHTML += `<div class="msg user">${i.value}</div>`;
            const t = i.value; i.value = '';
            const r = await fetch('/ask', {method:'POST', body:new URLSearchParams({'message':t, 'username':localStorage.getItem('rx_u')})});
            const d = await r.json();
            b.innerHTML += `<div class="msg ai">${d.answer}</div>`;
            b.scrollTop = b.scrollHeight;
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
