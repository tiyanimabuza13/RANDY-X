import os
import sqlite3
import random
import hashlib
import secrets
import logging
import google.generativeai as genai
from datetime import datetime
from flask import Flask, request, jsonify, render_template, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from deep_translator import GoogleTranslator

# -----------------------
# CONFIGURATION & SECURITY
# -----------------------
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Get from aistudio.google.com
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
DB_FILE = "randyx_ai.db"

if not GEMINI_API_KEY:
    print("⚠️ WARNING: GEMINI_API_KEY not set. AI will use fallback mode.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)
limiter = Limiter(app=app, key_func=get_remote_address)

# -----------------------
# DATABASE & AI LOGIC
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, language TEXT, premium INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, user_id INTEGER, message TEXT, response TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

init_db()

def get_ai_response(prompt, user_name, is_premium):
    if not GEMINI_API_KEY:
        return "I'm in offline mode. Please set my API Key to start chatting!"
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # System instructions to give it personality
        full_prompt = f"You are Randy-X AI, a helpful and witty assistant. The user's name is {user_name}. Provide a clear, helpful response to: {prompt}"
        
        response = model.generate_content(full_prompt)
        text = response.text
        
        # Trial users only get the first 150 characters
        if not is_premium:
            if len(text) > 150:
                text = text[:150] + "... [Upgrade to Premium for full answers!]"
        return text
    except Exception as e:
        return f"Error connecting to brain: {str(e)}"

# -----------------------
# ROUTES
# -----------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO users (name, language, premium) VALUES (?, ?, ?)", 
              (data['name'], data['language'], data.get('premium', 0)))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"user_id": user_id, "name": data['name'], "premium": data.get('premium', 0)})

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    user_id = data.get("user_id")
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    
    answer = get_ai_response(data['message'], user['name'] if user else "Guest", user['premium'] if user else 0)
    
    if user['language'] != 'en':
        try:
            answer = GoogleTranslator(source='auto', target=user['language']).translate(answer)
        except: pass

    conn.execute("INSERT INTO messages (user_id, message, response, timestamp) VALUES (?, ?, ?, ?)",
                 (user_id, data['message'], answer, datetime.now()))
    conn.commit()
    conn.close()
    
    return jsonify({"answer": answer})

# -----------------------
# UI DESIGN (THE BEAUTIFUL VERSION)
# -----------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Randy-X | Next Gen AI</title>
    <style>
        :root { --primary: #00d2ff; --secondary: #3a7bd5; }
        body { 
            margin: 0; 
            font-family: 'Inter', sans-serif;
            background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)), 
                        url('https://images.unsplash.com/photo-1451187580459-43490279c0fa?ixlib=rb-1.2.1&auto=format&fit=crop&w=1920&q=80');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            height: 100vh;
            display: flex; justify-content: center; align-items: center;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 24px;
            width: 90%; max-width: 900px; height: 80vh;
            display: flex; flex-direction: column; overflow: hidden;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
        }
        header { padding: 20px; text-align: center; color: white; border-bottom: 1px solid rgba(255,255,255,0.1); }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .msg { padding: 12px 18px; border-radius: 15px; max-width: 80%; color: white; line-height: 1.5; font-size: 15px; }
        .user { align-self: flex-end; background: var(--secondary); border-bottom-right-radius: 2px; }
        .ai { align-self: flex-start; background: rgba(255,255,255,0.15); border-bottom-left-radius: 2px; }
        .input-area { padding: 20px; background: rgba(0,0,0,0.2); display: flex; gap: 10px; }
        input { 
            flex: 1; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.3);
            padding: 12px 20px; border-radius: 30px; color: white; outline: none;
        }
        button { 
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            border: none; padding: 10px 25px; border-radius: 30px; color: white; font-weight: bold; cursor: pointer;
            transition: 0.3s;
        }
        button:hover { transform: scale(1.05); }
        #reg-form { position: absolute; inset: 0; background: rgba(0,0,0,0.85); display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 10; color: white; }
    </style>
</head>
<body>
    <div class="glass-card">
        <div id="reg-form">
            <h2>Welcome to Randy-X AI</h2>
            <input type="text" id="user-name" placeholder="Enter your name" style="width: 250px; margin-bottom: 10px;">
            <select id="user-lang" style="padding: 10px; border-radius: 10px; margin-bottom: 10px;">
                <option value="en">English</option>
                <option value="ts">Xitsonga</option>
            </select>
            <label><input type="checkbox" id="is-premium"> I am a Premium User</label><br>
            <button onclick="doRegister()">Launch AI</button>
        </div>
        <header><h1>Randy-X AI</h1></header>
        <div id="chat-box"></div>
        <div class="input-area">
            <input type="text" id="user-input" placeholder="Ask me anything...">
            <button onclick="send()">Send</button>
        </div>
    </div>

    <script>
        let userId = null;
        async function doRegister() {
            const name = document.getElementById('user-name').value;
            const lang = document.getElementById('user-lang').value;
            const prem = document.getElementById('is-premium').checked ? 1 : 0;
            const res = await fetch('/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, language: lang, premium: prem})
            });
            const data = await res.json();
            userId = data.user_id;
            document.getElementById('reg-form').style.display = 'none';
        }

        async function send() {
            const input = document.getElementById('user-input');
            const msg = input.value;
            if(!msg) return;
            
            const box = document.getElementById('chat-box');
            box.innerHTML += `<div class="msg user">${msg}</div>`;
            input.value = '';
            
            const res = await fetch('/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: msg, user_id: userId})
            });
            const data = await res.json();
            box.innerHTML += `<div class="msg ai">${data.answer}</div>`;
            box.scrollTop = box.scrollHeight;
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    if not os.path.exists("templates"): os.makedirs("templates")
    with open("templates/index.html", "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE)
    
    print("🚀 Randy-X AI is Live!")
    app.run(debug=False, host='0.0.0.0', port=5000)
