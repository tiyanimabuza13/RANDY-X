import os
import sqlite3
import random
from flask import Flask, request, jsonify, render_template, abort
from flask_cors import CORS
from deep_translator import GoogleTranslator
from markupsafe import escape
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------
# CONFIGURATION
# -----------------------
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Vutomi14@1")
DB_FILE = "randyx_ai.db"

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# -----------------------
# DATABASE SETUP
# -----------------------
def init_db():
    """Initialize database with proper schema"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    premium INTEGER DEFAULT 0
                )''')
    conn.commit()
    conn.close()

init_db()

# -----------------------
# HELPERS
# -----------------------
def translate_text(text, target_lang="en"):
    """Translate text with error handling"""
    try:
        if not text or len(text) < 1:
            return text
        translator = GoogleTranslator(source="auto", target=target_lang)
        result = translator.translate(text)
        return result if result else text
    except Exception as e:
        logger.warning(f"Translation error: {e}")
        return text

def check_admin(password):
    """Verify admin password"""
    return password == ADMIN_PASSWORD

def ai_response(message):
    """Generate AI response"""
    responses = [
        "I understand you.",
        "Could you clarify that?",
        "Interesting, tell me more!",
        "I am here to assist you.",
        "Thanks for sharing that."
    ]
    return random.choice(responses)

def get_user(user_id):
    """Get user from database with proper error handling"""
    try:
        if not isinstance(user_id, int) or user_id <= 0:
            return None
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, name, language, premium FROM users WHERE id=?", (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Database error: {e}")
        return None

def register_user(name, lang="en", premium=0):
    """Register new user with validation"""
    try:
        name = str(name).strip()[:100]
        lang = str(lang).strip()[:10]
        
        if not name or len(name) < 1:
            return None
        
        if lang not in ["en", "ts"]:
            lang = "en"
        
        premium = 1 if premium else 0
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO users (name, language, premium) VALUES (?, ?, ?)", (name, lang, premium))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return None

# -----------------------
# ROUTES
# -----------------------
@app.route("/")
def home():
    """Serve home page"""
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    """Handle chat messages"""
    try:
        data = request.get_json()
        message = str(data.get("message", "")).strip()
        user_lang = str(data.get("language", "en")).strip()
        user_id = data.get("user_id")
        
        if not message or len(message) < 1:
            return jsonify({"error": "Message required"}), 400
        
        if user_lang not in ["en", "ts"]:
            user_lang = "en"
        
        user = None
        is_premium = False
        
        if user_id:
            user = get_user(user_id)
            if user:
                is_premium = user[3] == 1
                user_lang = user[2]
        
        translated_msg = translate_text(message, "en")
        answer = ai_response(translated_msg)
        
        if not is_premium:
            answer = answer[:50] + "..."
        
        answer_translated = translate_text(answer, user_lang)
        return jsonify({"answer": answer_translated})
    except Exception as e:
        logger.error(f"Ask endpoint error: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/register", methods=["POST"])
def register():
    """Handle user registration"""
    try:
        data = request.get_json()
        name = str(data.get("name", "Guest")).strip()
        lang = str(data.get("language", "en")).strip()
        premium = 1 if data.get("premium") else 0
        
        user_id = register_user(name, lang, premium)
        
        if not user_id:
            return jsonify({"error": "Registration failed"}), 400
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "name": name,
            "premium": premium
        })
    except Exception as e:
        logger.error(f"Register endpoint error: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/admin", methods=["POST"])
def admin():
    """Admin endpoint"""
    try:
        data = request.get_json()
        password = data.get("password", "")
        if not check_admin(password):
            return abort(403)
        return jsonify({"status": "success", "message": "Admin features unlocked!"})
    except Exception as e:
        logger.error(f"Admin endpoint error: {e}")
        return abort(500)

def setup_project():
    """Create folders and HTML template"""
    if not os.path.exists("templates"):
        os.makedirs("templates")
    if not os.path.exists("static"):
        os.makedirs("static")
    
    index_path = os.path.join("templates", "index.html")
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Randy-X AI</title>
<script>
let currentUserId = null;
let isPremium = false;
let userLang = "en";

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

async function registerUser() {
    let name = document.getElementById("name").value.trim();
    if(!name) { alert("Name required"); return; }
    
    let premium = document.getElementById("premium").checked ? 1 : 0;
    let lang = document.querySelector('input[name="lang"]:checked').value;
    userLang = lang;
    
    try {
        let response = await fetch("/register", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: name, language: lang, premium: premium})
        });
        
        if(!response.ok) throw new Error("Registration failed");
        
        let data = await response.json();
        currentUserId = data.user_id;
        isPremium = data.premium === 1;
        
        let message = "<b>System:</b> Welcome " + escapeHtml(name) + "! " + 
                      (isPremium ? "Premium user" : "Trial user") + 
                      " | Language: " + lang + "<br>";
        document.getElementById("chat").innerHTML += message;
        document.getElementById("registerDiv").style.display = "none";
        document.getElementById("chatDiv").style.display = "block";
    } catch(e) {
        alert("Registration error: " + e.message);
    }
}

async function sendMessage() {
    let msg = document.getElementById("msg").value.trim();
    if(msg === "") return;
    
    try {
        let response = await fetch("/ask", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: msg, language: userLang, user_id: currentUserId})
        });
        
        if(!response.ok) throw new Error("Failed to get response");
        
        let data = await response.json();
        document.getElementById("chat").innerHTML += 
            "<b>You:</b> " + escapeHtml(msg) + "<br>" +
            "<b>Randy-X:</b> " + escapeHtml(data.answer) + "<br>";
        document.getElementById("msg").value = "";
        document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight;
    } catch(e) {
        alert("Error: " + e.message);
    }
}

function toggleLanguage() {
    userLang = userLang === "en" ? "ts" : "en";
    alert("Language switched to " + (userLang === "en" ? "English" : "Xitsonga"));
}

document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("msg").addEventListener("keypress", function(e) {
        if(e.key === "Enter") sendMessage();
    });
});
</script>
<style>
* { box-sizing: border-box; }
body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
.container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
h1 { color: #333; text-align: center; }
#chat { border: 1px solid #ddd; padding: 15px; height: 350px; overflow-y: auto; margin-bottom: 15px; background: #fafafa; border-radius: 4px; }
input[type="text"] { width: calc(100% - 90px); padding: 10px; border: 1px solid #ddd; border-radius: 4px; margin-right: 5px; }
button { padding: 10px 15px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
button:hover { background: #0056b3; }
#registerDiv { padding: 20px 0; }
label { display: inline-block; margin: 10px 10px 10px 0; }
input[type="checkbox"], input[type="radio"] { margin-right: 5px; }
#chatDiv { display: none; }
</style>
</head>
<body>
<div class="container">
<h1>🤖 Randy-X AI – Trial & Premium</h1>

<div id="registerDiv">
    <h3>Register Your Account</h3>
    <input type="text" id="name" placeholder="Your Name"><br><br>
    <label><input type="checkbox" id="premium"> Premium User</label><br>
    <p><strong>Language:</strong></p>
    <label><input type="radio" name="lang" value="en" checked> English</label>
    <label><input type="radio" name="lang" value="ts"> Xitsonga</label><br><br>
    <button onclick="registerUser()">Register</button>
</div>

<div id="chatDiv">
    <div id="chat"></div>
    <input type="text" id="msg" placeholder="Type your message...">
    <button onclick="sendMessage()">Send</button>
    <button onclick="toggleLanguage()">🌐 Switch Language</button>
</div>
</div>

</body>
</html>""")

setup_project()

# -----------------------
# RUN APP
# -----------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Randy-X AI (Trial & Premium, Xitsonga/English)")
    print("=" * 60)
    print("Running at http://127.0.0.1:5000/")
    print("=" * 60)
    app.run(debug=True)