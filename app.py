"""
SignalBot Home Base — Flask App (Multi-User Edition)
=====================================================
Now uses user_manager.py for:
  - Per-user authentication (hashed passphrases)
  - Per-user memory namespaces
  - Admin god mode panel
  - User management (add, ban, reset passphrase)
"""

import os
import json
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, abort
)
from user_manager import get_user_manager, UserContext
from code_reader import get_code_context, get_file_list_brief, get_file_context

# ══════════════════════════════════════════════════════════════════
# APP SETUP
# ══════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "signalbot-homebase-change-me")

# Initialize user manager on startup
user_mgr = get_user_manager()

# If no users exist yet, redirect to first-run setup
FIRST_RUN = user_mgr.get_user_count() == 0


# ══════════════════════════════════════════════════════════════════
# AUTH DECORATORS
# ══════════════════════════════════════════════════════════════════

def login_required(f):
    """Require any authenticated user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Require admin (god mode) user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def get_current_user_context() -> UserContext:
    """
    Get the UserContext for the currently logged-in user.
    This tells SignalBot which data directory to use.
    """
    username = session.get("username")
    if not username:
        return None
    try:
        return UserContext(username, user_mgr)
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════════
# HELPER: Read user-specific data files
# ══════════════════════════════════════════════════════════════════

def read_user_json(username: str, filename: str, default=None):
    """Read a JSON file from a user's data directory."""
    data = user_mgr.read_user_data(username, filename)
    return data if data is not None else default


# ══════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    # If no users exist, redirect to first-run setup
    if user_mgr.get_user_count() == 0:
        return redirect(url_for("first_run"))

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        passphrase = request.form.get("passphrase", "")

        profile = user_mgr.authenticate(name, passphrase)
        if profile:
            session["authenticated"] = True
            session["username"] = profile.username
            session["display_name"] = profile.display_name
            session["role"] = profile.role
            return redirect(url_for("dashboard"))

        # Check if banned
        sanitized = user_mgr._sanitize_username(name)
        user = user_mgr.get_user(sanitized)
        if user and user.is_banned:
            error = "This account has been suspended."
        else:
            error = "Wrong name or passphrase."

    return render_template("login.html", error=error)


@app.route("/first-run", methods=["GET", "POST"])
def first_run():
    """First-time setup: create admin account."""
    if user_mgr.get_user_count() > 0:
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        passphrase = request.form.get("passphrase", "").strip()

        if not name or not passphrase:
            error = "Name and passphrase are both required."
        else:
            profile = user_mgr.setup_first_admin(name, passphrase)
            if profile:
                session["authenticated"] = True
                session["username"] = profile.username
                session["display_name"] = profile.display_name
                session["role"] = profile.role
                return redirect(url_for("dashboard"))
            else:
                error = "Setup failed. Check terminal for details."

    return render_template("first_run.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════════
# MAIN PAGES
# ══════════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        user=session.get("display_name", "User"),
        role=session.get("role", "user"),
        is_admin=session.get("role") == "admin",
    )


@app.route("/chat")
@login_required
def chat():
    return render_template(
        "chat.html",
        user=session.get("display_name", "User"),
        role=session.get("role", "user"),
    )


# ══════════════════════════════════════════════════════════════════
# ADMIN PANEL (GOD MODE)
# ══════════════════════════════════════════════════════════════════

@app.route("/admin")
@admin_required
def admin_panel():
    """God mode: see all users and their stats."""
    users = user_mgr.get_all_users()
    user_stats = []
    for u in users:
        stats = user_mgr.get_user_stats(u.username)
        if stats:
            user_stats.append(stats)

    return render_template(
        "admin.html",
        user=session.get("display_name", "Admin"),
        user_stats=user_stats,
    )


@app.route("/admin/user/<username>")
@admin_required
def admin_user_detail(username):
    """God mode: view a specific user's data."""
    stats = user_mgr.get_user_stats(username)
    if not stats:
        abort(404)

    # Load their recent conversations
    memory = read_user_json(username, "memory_log.json", [])
    recent_memory = memory[-20:] if isinstance(memory, list) else []

    # Load their cognitive state
    cog_state = read_user_json(username, "cognitive_state.json", {})

    # Load their indelible facts
    facts_data = read_user_json(username, "indelible_facts.json", {})
    facts = facts_data.get("facts", []) if isinstance(facts_data, dict) else []

    return render_template(
        "admin_user.html",
        user=session.get("display_name", "Admin"),
        target=stats,
        recent_memory=recent_memory,
        cog_state=cog_state,
        facts=facts,
    )


# ══════════════════════════════════════════════════════════════════
# ADMIN API ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.route("/api/admin/add-user", methods=["POST"])
@admin_required
def api_admin_add_user():
    """Add a new user account."""
    data = request.get_json()
    name = data.get("name", "").strip()
    passphrase = data.get("passphrase", "").strip()
    role = data.get("role", "user")

    if not name or not passphrase:
        return jsonify({"error": "Name and passphrase required"}), 400

    if role not in ("user", "admin"):
        role = "user"

    profile = user_mgr.create_user(name, passphrase, role=role)
    if not profile:
        return jsonify({"error": "Username already taken or reserved"}), 400

    return jsonify({
        "ok": True,
        "username": profile.username,
        "display_name": profile.display_name,
        "role": profile.role,
    })


@app.route("/api/admin/set-role", methods=["POST"])
@admin_required
def api_admin_set_role():
    """Change a user's role (ban/unban/promote)."""
    data = request.get_json()
    username = data.get("username", "")
    new_role = data.get("role", "")

    if not username or new_role not in ("user", "admin", "banned"):
        return jsonify({"error": "Invalid username or role"}), 400

    # Don't let admin ban themselves
    if username == session.get("username") and new_role == "banned":
        return jsonify({"error": "You can't ban yourself"}), 400

    ok = user_mgr.set_role(username, new_role)
    if not ok:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"ok": True, "username": username, "role": new_role})


@app.route("/api/admin/reset-passphrase", methods=["POST"])
@admin_required
def api_admin_reset_passphrase():
    """Reset a user's passphrase."""
    data = request.get_json()
    username = data.get("username", "")
    new_passphrase = data.get("passphrase", "").strip()

    if not username or not new_passphrase:
        return jsonify({"error": "Username and new passphrase required"}), 400

    ok = user_mgr.change_passphrase(username, new_passphrase)
    if not ok:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"ok": True, "username": username})


@app.route("/api/admin/delete-user", methods=["POST"])
@admin_required
def api_admin_delete_user():
    """Delete a user account."""
    data = request.get_json()
    username = data.get("username", "")
    delete_data = data.get("delete_data", False)

    if not username:
        return jsonify({"error": "Username required"}), 400

    if username == session.get("username"):
        return jsonify({"error": "You can't delete yourself"}), 400

    ok = user_mgr.delete_user(username, delete_data=delete_data)
    if not ok:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"ok": True, "username": username})


@app.route("/api/admin/users")
@admin_required
def api_admin_list_users():
    """Get all users with stats (for admin panel refresh)."""
    users = user_mgr.get_all_users()
    result = []
    for u in users:
        stats = user_mgr.get_user_stats(u.username)
        if stats:
            result.append(stats)
    return jsonify({"users": result})


# ══════════════════════════════════════════════════════════════════
# USER API ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.route("/api/status")
@login_required
def api_status():
    """
    Status endpoint — reads from the logged-in user's data.
    Returns real cognitive state, message counts, fact counts.
    """
    username = session.get("username", "")
    cog = read_user_json(username, "cognitive_state.json", {})
    memory = read_user_json(username, "memory_log.json", [])
    facts_data = read_user_json(username, "indelible_facts.json", {})
    archive = read_user_json(username, "memory_archive.json", [])

    # Counts
    msg_count = len(memory) if isinstance(memory, list) else 0
    fact_count = len(facts_data.get("facts", [])) if isinstance(facts_data, dict) else 0
    archive_count = len(archive) if isinstance(archive, list) else 0

    # Determine cognitive state label
    curiosity = cog.get("curiosity", 0)
    frustration = cog.get("frustration", 0)
    engagement = cog.get("engagement", 0)
    confidence = cog.get("confidence", 0)

    if frustration > 0.7:
        cog_label = "FRUSTRATED"
    elif curiosity > 0.7 and engagement > 0.5:
        cog_label = "CURIOUS"
    elif engagement > 0.7 and confidence > 0.5:
        cog_label = "ENGAGED"
    elif engagement < 0.3:
        cog_label = "IDLE"
    else:
        cog_label = "ACTIVE"

    # Build cognitive detail for the bar chart
    tone = cog.get("tone", {})
    cognitive_detail = {
        "curiosity": curiosity,
        "frustration": frustration,
        "confidence": confidence,
        "engagement": engagement,
        "identity_adherence": cog.get("identity_adherence", 0),
        "cognitive_load": cog.get("cognitive_load", 0),
    }
    # Add tone dimensions if they exist
    if isinstance(tone, dict):
        cognitive_detail["tone_playful"] = tone.get("playful", 0)
        cognitive_detail["tone_formal"] = tone.get("formal", 0)
        cognitive_detail["tone_concise"] = tone.get("concise", 0)
        cognitive_detail["tone_warm"] = tone.get("warm", 0)

    # Detect model
    model_name = "unknown"
    try:
        import response_engine
        if getattr(response_engine, "USE_ANTHROPIC", False):
            model_name = getattr(response_engine, "ANTHROPIC_MODEL", "claude")
        elif getattr(response_engine, "USE_MISTRAL", False):
            model_name = getattr(response_engine, "MISTRAL_MODEL", "mistral")
        else:
            model_name = getattr(response_engine, "OLLAMA_MODEL", "local")
    except Exception:
        pass

    return jsonify({
        "bot_online": True,
        "messages_total": msg_count,
        "indelible_facts": fact_count,
        "archive_episodes": archive_count,
        "cognitive_state": cog_label,
        "cognitive_detail": cognitive_detail,
        "model": model_name,
        "user": session.get("display_name", "?"),
    })


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    """
    Chat endpoint — uses the logged-in user's data directory.
    """
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    username = session.get("username", "")
    ctx = get_current_user_context()
    if not ctx:
        return jsonify({"error": "Session expired. Please log in again."}), 401

    # ── Build prompt using user's data ──
    # Load user's recent memory
    memory_path = ctx.get_path("memory_log.json")
    try:
        memory_rows = json.loads(memory_path.read_text(encoding="utf-8"))
    except Exception:
        memory_rows = []

    recent = memory_rows[-12:] if memory_rows else []
    recent_text = ""
    for r in recent:
        recent_text += f"User: {r.get('user', '')}\n"
        recent_text += f"SignalBot: {r.get('bot', '')}\n---\n"

    # Load identity (shared global file)
    identity_path = ctx.get_path("signal_identity.txt")
    try:
        identity = identity_path.read_text(encoding="utf-8")
    except Exception:
        identity = "You are SignalBot. Clever, candid, and slightly irreverent."

    # Load user's indelible facts
    facts_path = ctx.get_path("indelible_facts.json")
    facts_text = ""
    try:
        facts_data = json.loads(facts_path.read_text(encoding="utf-8"))
        for f in facts_data.get("facts", []):
            facts_text += f"- {f.get('fact', '')}\n"
    except Exception:
        pass

    # Load user's cognitive state for tone
    cog_path = ctx.get_path("cognitive_state.json")
    tone = "Be candid, practical, and slightly irreverent."
    try:
        cog = json.loads(cog_path.read_text(encoding="utf-8"))
        if cog.get("frustration", 0) > 0.6:
            tone = "Be direct and solution-focused. Skip philosophy."
        elif cog.get("curiosity", 0) > 0.7:
            tone = "Follow rabbit holes. Ask deeper questions."
    except Exception:
        pass

    # Build prompt
    prompt_parts = [
        "### SYSTEM INSTRUCTIONS ###",
        identity,
        f"You are talking to {ctx.display_name}.",
        f"TONE: {tone}",
        "",
    ]

    if facts_text:
        prompt_parts.append("[INDELIBLE FACTS - NEVER FORGET]")
        prompt_parts.append(facts_text)
        prompt_parts.append("")

    # ── Code Reader trigger ──
    # "read code" → inject full source code context
    # "read code <filename>" → inject specific file
    msg_lower = user_msg.lower().strip()
    if msg_lower.startswith("read code"):
        parts = user_msg.strip().split(None, 2)  # ["read", "code", maybe_filename]
        if len(parts) >= 3:
            # Specific file requested
            code_ctx = get_file_context(parts[2])
        else:
            # Full codebase
            code_ctx = get_code_context()
        prompt_parts.append(code_ctx)
        prompt_parts.append("")

    prompt_parts.extend([
        "### RECENT CONVERSATION ###",
        recent_text if recent_text else "(new conversation)",
        "",
        f"User: {user_msg}",
        "SignalBot:",
    ])

    full_prompt = "\n".join(prompt_parts)

    # ── Generate response ──
    try:
        from response_engine import generate_response
        reply = generate_response(full_prompt)
    except Exception as e:
        reply = f"[Error generating response: {e}]"

    # ── Save to user's memory log ──
    memory_rows.append({
        "ts": time.time(),
        "user": user_msg,
        "bot": reply,
    })
    try:
        memory_path.write_text(
            json.dumps(memory_rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[ERROR] Failed to save memory for {username}: {e}")

    # ── Update user's cognitive state ──
    try:
        cog_data = json.loads(cog_path.read_text(encoding="utf-8"))
        u = user_msg.lower()

        # Simple state updates (matches cognitive_state.py logic)
        if any(w in u for w in ["wrong", "no", "fix", "broken"]):
            cog_data["frustration"] = min(1.0, cog_data.get("frustration", 0.2) + 0.25)
        else:
            f = cog_data.get("frustration", 0.2)
            cog_data["frustration"] = f * 0.9 + 0.2 * 0.1

        if any(w in u for w in ["why", "how", "what if", "wonder", "curious"]):
            cog_data["curiosity"] = min(1.0, cog_data.get("curiosity", 0.8) + 0.2)
        elif any(w in u for w in ["ok", "thanks", "got it"]):
            cog_data["curiosity"] = max(0.3, cog_data.get("curiosity", 0.8) - 0.15)

        if any(w in u for w in ["perfect", "great", "exactly", "yes"]):
            cog_data["confidence"] = min(1.0, cog_data.get("confidence", 0.6) + 0.15)

        cog_data["last_update"] = time.time()

        cog_path.write_text(
            json.dumps(cog_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

    # ── Indelible fact detection ──
    try:
        ul = user_msg.lower()
        new_fact = None

        if "my name is" in ul:
            parts = ul.split("my name is", 1)
            if len(parts) == 2:
                name = parts[1].strip().split()[0].strip(".,!?")
                if name and len(name) > 1:
                    new_fact = {"fact": f"User's name is {name.capitalize()}", "category": "name"}

        if "remember that" in ul or "never forget" in ul:
            for trigger in ("remember that", "never forget"):
                if trigger in ul:
                    parts = ul.split(trigger, 1)
                    if len(parts) == 2 and len(parts[1].strip()) > 3:
                        new_fact = {"fact": parts[1].strip(), "category": "directive"}

        if new_fact:
            facts_data = json.loads(facts_path.read_text(encoding="utf-8"))
            import hashlib
            fact_id = hashlib.md5(new_fact["fact"].lower().encode()).hexdigest()[:12]

            existing_ids = {f.get("id") for f in facts_data.get("facts", [])}
            if fact_id not in existing_ids:
                facts_data["facts"].append({
                    "id": fact_id,
                    "fact": new_fact["fact"],
                    "category": new_fact["category"],
                    "first_mentioned": time.time(),
                    "last_confirmed": time.time(),
                    "confirmation_count": 1,
                    "locked": True,
                    "importance": 5.0,
                })
                facts_data["last_updated"] = time.time()
                facts_path.write_text(
                    json.dumps(facts_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
    except Exception:
        pass

    return jsonify({
        "reply": reply,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "sender": "SignalBot",
    })


@app.route("/api/activity")
@login_required
def api_activity():
    """Activity log — now reads from user's memory for real events."""
    username = session.get("username", "")
    memory = read_user_json(username, "memory_log.json", [])

    events = []
    if isinstance(memory, list):
        for row in memory[-7:]:
            ts = row.get("ts", 0)
            user_msg = row.get("user", "")[:40]
            try:
                t = datetime.fromtimestamp(ts).strftime("%H:%M")
            except Exception:
                t = "?"
            events.append({"time": t, "event": f"Chat: \"{user_msg}\""})

    if not events:
        events = [{"time": "—", "event": "No conversations yet"}]

    events.reverse()
    return jsonify({"events": events})


# ══════════════════════════════════════════════════════════════════
# THEME SYSTEM
# ══════════════════════════════════════════════════════════════════

# Accent color palettes: name → (accent, accent-hover)
ACCENT_COLORS = {
    "green":  ("#00ff9d", "#00e88a"),
    "blue":   ("#4dabf7", "#339af0"),
    "purple": ("#b197fc", "#9775fa"),
    "pink":   ("#f783ac", "#e64980"),
    "orange": ("#ffa94d", "#ff922b"),
    "red":    ("#ff6b6b", "#fa5252"),
    "cyan":   ("#3bc9db", "#22b8cf"),
}

# Background palettes: name → (bg, surface, surface2, border)
BG_COLORS = {
    "dark":      ("#0a0a0f", "#111118", "#16161f", "#1e1e2e"),
    "midnight":  ("#0b0d1a", "#101325", "#151830", "#1c2040"),
    "charcoal":  ("#121212", "#1a1a1a", "#222222", "#2a2a2a"),
    "abyss":     ("#050508", "#0a0a10", "#0e0e18", "#151522"),
}


@app.context_processor
def inject_theme():
    """Make theme CSS variables available to every template."""
    username = session.get("username", "")
    profile = user_mgr.get_user(username) if username else None

    accent_name = getattr(profile, "theme_accent", "green") if profile else "green"
    bg_name = getattr(profile, "theme_bg", "dark") if profile else "dark"

    accent, accent_hover = ACCENT_COLORS.get(accent_name, ACCENT_COLORS["green"])
    bg, surface, surface2, border = BG_COLORS.get(bg_name, BG_COLORS["dark"])

    return {
        "theme_css": (
            f"--accent:{accent};--accent-hover:{accent_hover};"
            f"--bg:{bg};--surface:{surface};--surface2:{surface2};--border:{border};"
        ),
        "theme_accent": accent_name,
        "theme_bg": bg_name,
    }


@app.route("/api/theme", methods=["POST"])
@login_required
def api_set_theme():
    """Save user's theme preference."""
    data = request.get_json()
    accent = data.get("accent", "")
    bg = data.get("bg", "")
    username = session.get("username", "")

    ok = user_mgr.set_theme(username, accent=accent, bg=bg)
    if not ok:
        return jsonify({"error": "Failed to save theme"}), 400

    return jsonify({"ok": True, "accent": accent, "bg": bg})


# ══════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"[APP] Users registered: {user_mgr.get_user_count()}")
    for u in user_mgr.get_all_users():
        print(f"  [{u.role:6s}] {u.display_name} ({u.username})")

    if user_mgr.get_user_count() == 0:
        print("[APP] No users found — first-run setup will appear in browser.")

    app.run(host="0.0.0.0", port=5000, debug=False)
