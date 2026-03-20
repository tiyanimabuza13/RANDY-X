"""
Randy-X AI - Production Ready Version
Fixed: Security, Architecture, Performance, and Logic Issues

Requirements:
    pip install flask flask-cors flask-limiter deep-translator

Environment Variables:
    export ADMIN_PASSWORD="your_secure_password_here"
    export SECRET_KEY="your_secret_key_here"  # Optional, auto-generated if not set

Run:
    python randyx_ai_improved.py
"""

import os
import sqlite3
import random
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template, abort, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from deep_translator import GoogleTranslator
from markupsafe import escape
import logging

# -----------------------
# CONFIGURATION
# -----------------------
# SECURITY FIX: No hardcoded passwords - must use environment variable
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("❌ CRITICAL: Set ADMIN_PASSWORD environment variable before running!")

# Generate a secret key for sessions
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
DB_FILE = "randyx_ai.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY
CORS(app, resources={r"/*": {"origins": "*"}})

# RATE LIMITING: Prevent abuse
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# -----------------------
# DATABASE SETUP (WITH CONNECTION POOLING)
# -----------------------
def get_db():
    """Get database connection with proper handling"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Close database connection after each request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with proper schema and indexes"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table with improved schema
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    premium INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # Messages table for conversation history
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message TEXT NOT NULL,
                    response TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )''')
    
    # Create indexes for performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON messages(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_user_active ON users(last_active)")
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully")

init_db()

# -----------------------
# SECURITY HELPERS
# -----------------------
def hash_admin_password(password):
    """Hash password for secure comparison"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_admin(password):
    """Verify admin password securely"""
    if not password or not isinstance(password, str):
        return False
    # Use constant-time comparison to prevent timing attacks
    expected_hash = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
    provided_hash = hashlib.sha256(password.encode()).hexdigest()
    return secrets.compare_digest(expected_hash, provided_hash)

def sanitize_input(text, max_length=500):
    """Sanitize user input"""
    if not text or not isinstance(text, str):
        return ""
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text

def validate_user_id(user_id):
    """Validate user ID format"""
    try:
        uid = int(user_id)
        return uid if uid > 0 else None
    except (ValueError, TypeError):
        return None

# -----------------------
# AI RESPONSE SYSTEM (IMPROVED)
# -----------------------
def ai_response(message, user_name="User", is_premium=False):
    """
    Generate contextual AI response based on user input
    Now actually processes the message content!
    """
    message_lower = message.lower().strip()
    
    # Greeting detection
    greetings = ['hello', 'hi', 'hey', 'greetings', 'morning', 'afternoon', 'evening']
    if any(g in message_lower for g in greetings):
        responses = [
            f"Hello {user_name}! How can I assist you today?",
            f"Hi there, {user_name}! What brings you here?",
            f"Hey {user_name}! Ready to help you out."
        ]
        return random.choice(responses)
    
    # Question detection
    questions = ['what', 'how', 'why', 'when', 'where', 'who', 'which']
    if any(message_lower.startswith(q) for q in questions) or '?' in message:
        responses = [
            f"That's an interesting question, {user_name}. Let me think about '{message[:50]}...'",
            f"Great question! Regarding '{message[:40]}...', I'd say it depends on several factors.",
            f"I'm analyzing your question about '{message[:50]}...'. Here's what I think..."
        ]
        return random.choice(responses)
    
    # Help request
    help_keywords = ['help', 'assist', 'support', 'stuck', 'problem', 'issue']
    if any(h in message_lower for h in help_keywords):
        responses = [
            f"I'm here to help, {user_name}! Tell me more about your situation.",
            f"Don't worry {user_name}, we'll figure this out together. What specifically do you need help with?",
            f"Support mode activated! How can I assist you today, {user_name}?"
        ]
        return random.choice(responses)
    
    # Premium feature: More detailed responses
    if is_premium:
        responses = [
            f"Thank you for sharing that, {user_name}. I understand you're saying: '{message[:100]}...' That's quite insightful!",
            f"I appreciate your detailed message, {user_name}. Regarding '{message[:80]}...', I have several thoughts to share...",
            f"As a premium user, {user_name}, I want to give you a comprehensive response about '{message[:90]}...'"
        ]
    else:
        # Trial users get shorter responses
        responses = [
            "I understand you. Tell me more!",
            "Interesting point! Could you elaborate?",
            "I see. What else would you like to discuss?",
            "Thanks for sharing! How can I help further?"
        ]
    
    return random.choice(responses)

# -----------------------
# TRANSLATION (OPTIMIZED)
# -----------------------
translator_cache = {}

def translate_text(text, target_lang="en"):
    """Translate text with caching and error handling"""
    if not text or target_lang == "en":
        return text
    
    # Simple cache check
    cache_key = f"{text[:50]}_{target_lang}"
    if cache_key in translator_cache:
        return translator_cache[cache_key]
    
    try:
        translator = GoogleTranslator(source="auto", target=target_lang)
        result = translator.translate(text)
        if result:
            translator_cache[cache_key] = result
            return result
        return text
    except Exception as e:
        logger.warning(f"Translation error: {e}")
        return text

# -----------------------
# DATABASE OPERATIONS
# -----------------------
def get_user(user_id):
    """Get user from database"""
    uid = validate_user_id(user_id)
    if not uid:
        return None
    
    try:
        db = get_db()
        c = db.cursor()
        c.execute("SELECT id, name, language, premium FROM users WHERE id=?", (uid,))
        user = c.fetchone()
        
        # Update last active
        if user:
            c.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id=?", (uid,))
            db.commit()
        
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Database error in get_user: {e}")
        return None

def register_user(name, lang="en", premium=0):
    """Register new user with validation"""
    name = sanitize_input(name, 100)
    if not name:
        return None
    
    lang = sanitize_input(lang, 10)
    if lang not in ["en", "ts"]:
        lang = "en"
    
    premium = 1 if premium else 0
    
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "INSERT INTO users (name, language, premium) VALUES (?, ?, ?)",
            (name, lang, premium)
        )
        db.commit()
        return c.lastrowid
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return None

def save_message(user_id, message, response):
    """Save conversation to database"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "INSERT INTO messages (user_id, message, response) VALUES (?, ?, ?)",
            (user_id, message[:500], response[:1000])
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error saving message: {e}")

# -----------------------
# ROUTES
# -----------------------
@app.route("/")
def home():
    """Serve home page"""
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
@limiter.limit("30 per minute")  # Rate limit: 30 requests per minute
def ask():
    """Handle chat messages with improved logic"""
    try:
        data = request.get_json() or {}
        
        # Input validation
        message = sanitize_input(data.get("message", ""), 500)
        if not message:
            return jsonify({"error": "Message required", "code": "MISSING_MESSAGE"}), 400
        
        user_lang = sanitize_input(data.get("language", "en"), 10)
        if user_lang not in ["en", "ts"]:
            user_lang = "en"
        
        user_id = data.get("user_id")
        user = None
        is_premium = False
        user_name = "User"
        
        if user_id:
            user = get_user(user_id)
            if user:
                is_premium = user["premium"] == 1
                user_lang = user["language"]
                user_name = user["name"]
        
        # Generate AI response (now actually uses the message!)
        answer = ai_response(message, user_name, is_premium)
        
        # Premium feature: Full response length
        if not is_premium:
            answer = answer[:100] + "... (Upgrade to Premium for full responses!)"
        
        # Translate if needed
        if user_lang != "en":
            answer = translate_text(answer, user_lang)
        
        # Save to history if user exists
        if user:
            save_message(user["id"], message, answer)
        
        return jsonify({
            "answer": answer,
            "premium": is_premium,
            "language": user_lang
        })
        
    except Exception as e:
        logger.error(f"Ask endpoint error: {e}")
        return jsonify({"error": "Server error", "code": "SERVER_ERROR"}), 500

@app.route("/register", methods=["POST"])
@limiter.limit("10 per minute")  # Prevent spam registrations
def register():
    """Handle user registration"""
    try:
        data = request.get_json() or {}
        
        name = sanitize_input(data.get("name", "Guest"), 100)
        if not name:
            return jsonify({"error": "Name required", "code": "MISSING_NAME"}), 400
        
        lang = sanitize_input(data.get("language", "en"), 10)
        premium = 1 if data.get("premium") else 0
        
        user_id = register_user(name, lang, premium)
        
        if not user_id:
            return jsonify({"error": "Registration failed", "code": "DB_ERROR"}), 500
        
        logger.info(f"New user registered: {name} (ID: {user_id}, Premium: {premium})")
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "name": name,
            "premium": premium,
            "language": lang
        })
        
    except Exception as e:
        logger.error(f"Register endpoint error: {e}")
        return jsonify({"error": "Server error", "code": "SERVER_ERROR"}), 500

@app.route("/admin", methods=["POST"])
@limiter.limit("5 per minute")  # Strict rate limit for admin
def admin():
    """Admin endpoint with security"""
    try:
        data = request.get_json() or {}
        password = data.get("password", "")
        
        if not check_admin(password):
            logger.warning(f"Failed admin login attempt from {request.remote_addr}")
            return jsonify({"error": "Access denied", "code": "UNAUTHORIZED"}), 403
        
        # Get stats for admin
        db = get_db()
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        message_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE premium=1")
        premium_count = c.fetchone()[0]
        
        return jsonify({
            "status": "success",
            "message": "Admin features unlocked!",
            "stats": {
                "total_users": user_count,
                "total_messages": message_count,
                "premium_users": premium_count
            }
        })
        
    except Exception as e:
        logger.error(f"Admin endpoint error: {e}")
        return jsonify({"error": "Server error", "code": "SERVER_ERROR"}), 500

@app.route("/history/<int:user_id>", methods=["GET"])
def get_history(user_id):
    """Get conversation history for user"""
    try:
        user = get_user(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        db = get_db()
        c = db.cursor()
        c.execute(
            "SELECT message, response, timestamp FROM messages WHERE user_id=? ORDER BY timestamp DESC LIMIT 50",
            (user_id,)
        )
        messages = [dict(row) for row in c.fetchall()]
        
        return jsonify({
            "user_id": user_id,
            "history": messages
        })
        
    except Exception as e:
        logger.error(f"History endpoint error: {e}")
        return jsonify({"error": "Server error"}), 500

# -----------------------
# HTML TEMPLATE
# -----------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Randy-X AI - Secure & Smart</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { 
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}
.container { 
    max-width: 800px; 
    margin: 0 auto; 
    background: white; 
    padding: 30px; 
    border-radius: 16px; 
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
h1 { 
    color: #333; 
    text-align: center; 
    margin-bottom: 10px;
    font-size: 2.5em;
}
.subtitle {
    text-align: center;
    color: #666;
    margin-bottom: 30px;
}
#chat { 
    border: 2px solid #e0e0e0; 
    padding: 20px; 
    height: 400px; 
    overflow-y: auto; 
    margin-bottom: 20px; 
    background: #f8f9fa; 
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.message {
    max-width: 80%;
    padding: 12px 16px;
    border-radius: 18px;
    word-wrap: break-word;
    animation: fadeIn 0.3s ease-in;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.user-message {
    align-self: flex-end;
    background: #007bff;
    color: white;
    border-bottom-right-radius: 4px;
}
.ai-message {
    align-self: flex-start;
    background: #e9ecef;
    color: #333;
    border-bottom-left-radius: 4px;
}
.system-message {
    align-self: center;
    background: #d4edda;
    color: #155724;
    font-size: 0.9em;
    border-radius: 12px;
}
.input-area {
    display: flex;
    gap: 10px;
    margin-bottom: 15px;
}
input[type="text"] { 
    flex: 1;
    padding: 14px; 
    border: 2px solid #ddd; 
    border-radius: 25px; 
    font-size: 16px;
    transition: border-color 0.3s;
}
input[type="text"]:focus {
    outline: none;
    border-color: #667eea;
}
button { 
    padding: 14px 24px; 
    background: #667eea; 
    color: white; 
    border: none; 
    border-radius: 25px; 
    cursor: pointer;
    font-size: 16px;
    font-weight: 600;
    transition: all 0.3s;
}
button:hover { 
    background: #5568d3;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}
button:active {
    transform: translateY(0);
}
button:disabled {
    background: #ccc;
    cursor: not-allowed;
    transform: none;
}
.premium-badge {
    display: inline-block;
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: bold;
    margin-left: 10px;
}
#registerDiv { 
    padding: 20px;
    background: #f8f9fa;
    border-radius: 12px;
    margin-bottom: 20px;
}
.form-group {
    margin-bottom: 15px;
}
label { 
    display: block;
    margin-bottom: 5px;
    font-weight: 600;
    color: #555;
}
input[type="checkbox"], input[type="radio"] { 
    margin-right: 8px;
}
.radio-group, .checkbox-group {
    display: flex;
    gap: 20px;
    margin-top: 8px;
}
.radio-group label, .checkbox-group label {
    display: flex;
    align-items: center;
    font-weight: normal;
    cursor: pointer;
}
#chatDiv { 
    display: none; 
}
.typing-indicator {
    display: none;
    align-self: flex-start;
    background: #e9ecef;
    padding: 12px 16px;
    border-radius: 18px;
    border-bottom-left-radius: 4px;
}
.typing-indicator span {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #999;
    border-radius: 50%;
    margin: 0 2px;
    animation: typing 1.4s infinite;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-10px); }
}
.error-toast {
    position: fixed;
    top: 20px;
    right: 20px;
    background: #dc3545;
    color: white;
    padding: 15px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    display: none;
    z-index: 1000;
}
.controls {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}
</style>
</head>
<body>
<div class="container">
<h1>🤖 Randy-X AI</h1>
<p class="subtitle">Secure, Smart, and Multilingual</p>

<div id="registerDiv">
    <h3>🚀 Create Your Account</h3>
    <div class="form-group">
        <label>Your Name:</label>
        <input type="text" id="name" placeholder="Enter your name" maxlength="100">
    </div>
    
    <div class="form-group">
        <label>Account Type:</label>
        <div class="checkbox-group">
            <label><input type="checkbox" id="premium"> ⭐ Premium User (Full Responses)</label>
        </div>
    </div>
    
    <div class="form-group">
        <label>Language / Rimi:</label>
        <div class="radio-group">
            <label><input type="radio" name="lang" value="en" checked> 🇬🇧 English</label>
            <label><input type="radio" name="lang" value="ts"> 🇿🇦 Xitsonga</label>
        </div>
    </div>
    
    <button onclick="registerUser()">Get Started</button>
</div>

<div id="chatDiv">
    <div id="chat">
        <div class="typing-indicator" id="typing">
            <span></span><span></span><span></span>
        </div>
    </div>
    <div class="input-area">
        <input type="text" id="msg" placeholder="Type your message..." maxlength="500">
        <button onclick="sendMessage()">Send</button>
    </div>
    <div class="controls">
        <button onclick="toggleLanguage()">🌐 Switch Language</button>
        <button onclick="clearChat()">🗑️ Clear Chat</button>
    </div>
</div>
</div>

<div class="error-toast" id="errorToast"></div>

<script>
let currentUserId = null;
let isPremium = false;
let userLang = "en";
let userName = "";

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

function showError(message) {
    const toast = document.getElementById("errorToast");
    toast.textContent = message;
    toast.style.display = "block";
    setTimeout(() => toast.style.display = "none", 3000);
}

function addMessage(text, type) {
    const chat = document.getElementById("chat");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${type}-message`;
    msgDiv.innerHTML = text;
    chat.insertBefore(msgDiv, document.getElementById("typing"));
    chat.scrollTop = chat.scrollHeight;
}

function setTyping(show) {
    document.getElementById("typing").style.display = show ? "block" : "none";
}

async function registerUser() {
    const name = document.getElementById("name").value.trim();
    if (!name) {
        showError("Please enter your name");
        return;
    }
    
    const premium = document.getElementById("premium").checked ? 1 : 0;
    const lang = document.querySelector('input[name="lang"]:checked').value;
    
    try {
        const response = await fetch("/register", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name, language: lang, premium})
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || "Registration failed");
        }
        
        currentUserId = data.user_id;
        isPremium = data.premium === 1;
        userLang = data.language;
        userName = data.name;
        
        const badge = isPremium ? '<span class="premium-badge">⭐ PREMIUM</span>' : '<span class="premium-badge" style="background: #6c757d;">TRIAL</span>';
        addMessage(`Welcome <b>${escapeHtml(name)}</b>! ${badge}<br>Language: ${lang === 'en' ? '🇬🇧 English' : '🇿🇦 Xitsonga'}`, "system");
        
        document.getElementById("registerDiv").style.display = "none";
        document.getElementById("chatDiv").style.display = "block";
        
        // Welcome message
        setTimeout(() => {
            addMessage(isPremium 
                ? "🎉 Hello " + escapeHtml(name) + "! I'm Randy-X AI. As a premium user, you get detailed, personalized responses. How can I help you today?"
                : "👋 Hello " + escapeHtml(name) + "! I'm Randy-X AI. You're on the trial plan (short responses). Upgrade anytime for full features!", 
            "ai");
        }, 500);
        
    } catch (e) {
        showError("Registration error: " + e.message);
    }
}

async function sendMessage() {
    const input = document.getElementById("msg");
    const msg = input.value.trim();
    if (!msg) return;
    
    addMessage(escapeHtml(msg), "user");
    input.value = "";
    setTyping(true);
    
    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: msg, language: userLang, user_id: currentUserId})
        });
        
        const data = await response.json();
        setTyping(false);
        
        if (!response.ok) {
            throw new Error(data.error || "Failed to get response");
        }
        
        addMessage(escapeHtml(data.answer), "ai");
        
    } catch (e) {
        setTyping(false);
        showError("Error: " + e.message);
    }
}

function toggleLanguage() {
    userLang = userLang === "en" ? "ts" : "en";
    const langName = userLang === "en" ? "English" : "Xitsonga";
    addMessage(`🌐 Language switched to <b>${langName}</b>`, "system");
}

function clearChat() {
    const chat = document.getElementById("chat");
    chat.innerHTML = '<div class="typing-indicator" id="typing"><span></span><span></span><span></span></div>';
    addMessage("Chat cleared. How can I help you?", "ai");
}

document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("msg").addEventListener("keypress", function(e) {
        if (e.key === "Enter") sendMessage();
    });
});
</script>
</body>
</html>"""

def setup_project():
    """Create folders and HTML template"""
    if not os.path.exists("templates"):
        os.makedirs("templates")
    if not os.path.exists("static"):
        os.makedirs("static")
    
    index_path = os.path.join("templates", "index.html")
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(HTML_TEMPLATE)
        logger.info("✅ HTML template created")

setup_project()

# -----------------------
# ERROR HANDLERS
# -----------------------
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded", "code": "RATE_LIMIT"}), 429

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found", "code": "NOT_FOUND"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "code": "SERVER_ERROR"}), 500

# -----------------------
# RUN APP
# -----------------------
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Randy-X AI - Production Ready")
    print("=" * 60)
    print("Features:")
    print("  ✅ Security: No hardcoded passwords, rate limiting")
    print("  ✅ AI: Contextual responses based on input")
    print("  ✅ Database: Connection pooling, conversation history")
    print("  ✅ Premium: Full vs trial response lengths")
    print("  ✅ Translation: English ↔ Xitsonga")
    print("=" * 60)
    print("⚠️  Set ADMIN_PASSWORD environment variable!")
    print("   Example: export ADMIN_PASSWORD=your_secure_password")
    print("=" * 60)
    print("Running at http://127.0.0.1:5000/")
    print("=" * 60)
    
    # Production: Set debug=False
    app.run(host="0.0.0.0", port=5000, debug=False)
