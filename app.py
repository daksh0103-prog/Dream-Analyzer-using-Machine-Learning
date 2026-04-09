import os
import secrets
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from dotenv import load_dotenv
from datetime import datetime
import requests as http_requests
import database as db
from ai_model import DreamAI

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

ai = DreamAI()


# ── Init DB lazily (safe for Vercel serverless) ────────────────────────────────
@app.before_request
def initialize_database():
    if not getattr(app, '_db_initialized', False):
        db.init_db()
        app._db_initialized = True


# ── Auth helpers ───────────────────────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        if not username or not password:
            flash("Username and password are required.", "error")
        elif db.get_user(username):
            flash("Username already taken.", "error")
        else:
            db.create_user(username, password)
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        user = db.verify_password(username, password)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Main routes ────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    result = None
    if request.method == "POST":
        dream_text = request.form.get("dream", "").strip()
        if not dream_text:
            flash("Please enter your dream.", "error")
            return redirect(url_for("index"))

        interpretation = ai.interpret(dream_text)
        emotion = ai.analyze_emotion(dream_text)
        symbols = ai.extract_symbols(dream_text)

        try:
            sleep_quality = int(request.form.get("sleep_quality", 0)) or None
        except (ValueError, TypeError):
            sleep_quality = None

        dream_id = db.save_dream(
            user_id=session["user_id"],
            text=dream_text,
            interpretation=interpretation,
            emotion_primary=emotion["primary"],
            emotion_secondary=emotion["secondary"],
            confidence_primary=emotion["confidence_primary"],
            confidence_secondary=emotion["confidence_secondary"],
            sleep_quality=sleep_quality,
            symbols=symbols,
        )
        result = {
            "id": dream_id,
            "text": dream_text,
            "interpretation": interpretation,
            "emotion": emotion,
            "symbols": symbols,
            "sleep_quality": sleep_quality,
        }

    import json
    recent_dreams = db.get_dreams(session["user_id"], limit=4)
    top_symbols   = db.get_top_symbols(session["user_id"], limit=3)
    all_dreams    = db.get_dreams(session["user_id"], limit=90)
    dream_dates   = list({str(d["created_at"].date()) for d in all_dreams if d["created_at"]})
    dream_dates_json = json.dumps(dream_dates)

    return render_template(
        "index.html",
        result=result,
        recent_dreams=recent_dreams,
        top_symbols=top_symbols,
        dream_dates_json=dream_dates_json,
    )


@app.route("/history")
@login_required
def history():
    dreams = db.get_dreams(session["user_id"])
    streak = db.get_streak(session["user_id"])
    return render_template("history.html", dreams=dreams, streak=streak)


@app.route("/edit/<int:dream_id>", methods=["GET", "POST"])
@login_required
def edit_dream(dream_id):
    dream = db.get_dream(dream_id, session["user_id"])
    if not dream:
        flash("Dream not found.", "error")
        return redirect(url_for("history"))

    if request.method == "POST":
        text = request.form.get("dream", "").strip()
        if not text:
            flash("Dream text cannot be empty.", "error")
            return redirect(url_for("edit_dream", dream_id=dream_id))

        interpretation = ai.interpret(text)
        emotion = ai.analyze_emotion(text)
        symbols = ai.extract_symbols(text)
        try:
            sleep_quality = int(request.form.get("sleep_quality", 0)) or None
        except (ValueError, TypeError):
            sleep_quality = None
        db.update_dream(
            dream_id, session["user_id"], text, interpretation,
            emotion["primary"], emotion["secondary"],
            emotion["confidence_primary"], emotion["confidence_secondary"],
            sleep_quality=sleep_quality, symbols=symbols,
        )
        flash("Dream updated!", "success")
        return redirect(url_for("history"))

    return render_template("edit_dream.html", dream=dream)


@app.route("/delete/<int:dream_id>", methods=["POST"])
@login_required
def delete_dream(dream_id):
    db.delete_dream(dream_id, session["user_id"])
    flash("Dream deleted.", "success")
    return redirect(url_for("history"))


@app.route("/analytics")
@login_required
def analytics():
    dreams = db.get_dreams(session["user_id"])
    emotion_counts = db.get_emotion_counts(session["user_id"])
    streak = db.get_streak(session["user_id"])
    mood_calendar = db.get_mood_calendar(session["user_id"])
    sleep_data = db.get_sleep_emotion_data(session["user_id"])
    top_symbols = db.get_top_symbols(session["user_id"])
    total = len(dreams)

    # Personality insight based on dominant emotion
    dominant = emotion_counts[0]["emotion"] if emotion_counts else "neutral"
    personality_map = {
        "joy":      ("The Optimist",      "You tend to dream of light and possibility. Your subconscious radiates warmth and hope."),
        "sadness":  ("The Deep Feeler",   "Your dreams process emotion richly. You have profound empathy and inner depth."),
        "fear":     ("The Vigilant",      "Your mind is alert and protective. You are cautious, perceptive, and growth-oriented."),
        "anger":    ("The Passionate",    "Intensity fuels you. Your dreams reflect strong values and a desire for justice."),
        "surprise": ("The Curious One",   "Your mind craves novelty. You are adaptable, open, and endlessly intrigued by life."),
        "disgust":  ("The Discerning",    "You have high standards. Your dreams reveal a refined sense of right and wrong."),
        "neutral":  ("The Balanced Soul", "Your dreams are calm and grounded. You carry a steady, centred inner world."),
    }
    personality_title, personality_desc = personality_map.get(
        dominant, personality_map["neutral"]
    )

    # Sleep-emotion correlation: avg sleep per emotion
    sleep_by_emotion = {}
    for row in sleep_data:
        e = row["emotion_primary"] or "neutral"
        sleep_by_emotion.setdefault(e, []).append(row["sleep_quality"])
    sleep_emotion_avg = {
        e: round(sum(v) / len(v), 1)
        for e, v in sleep_by_emotion.items()
    }

    # Mood calendar: convert to {date_str: emotion}
    mood_map = {str(r["day"]): r["emotion"] for r in mood_calendar}

    return render_template(
        "analytics.html",
        dreams=dreams,
        emotion_counts=emotion_counts,
        streak=streak,
        total=total,
        personality_title=personality_title,
        personality_desc=personality_desc,
        dominant_emotion=dominant,
        mood_map=mood_map,
        sleep_data=[dict(r) for r in sleep_data],
        sleep_emotion_avg=sleep_emotion_avg,
        top_symbols=top_symbols,
    )


# ── OAuth ──────────────────────────────────────────────────────────────────────

@app.route("/auth/google")
def oauth_google():
    """Redirect user to Google's OAuth consent screen."""
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = {
        "client_id":     os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri":  url_for("oauth_google_callback", _external=True),
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
    }
    from urllib.parse import urlencode
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@app.route("/auth/google/callback")
def oauth_google_callback():
    """Handle Google's redirect back after user consents."""
    error = request.args.get("error")
    if error:
        flash(f"Google login cancelled: {error}", "error")
        return redirect(url_for("login"))

    if request.args.get("state") != session.pop("oauth_state", None):
        flash("Invalid OAuth state. Please try again.", "error")
        return redirect(url_for("login"))

    code = request.args.get("code")
    # Exchange code for tokens
    token_resp = http_requests.post("https://oauth2.googleapis.com/token", data={
        "code":          code,
        "client_id":     os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri":  url_for("oauth_google_callback", _external=True),
        "grant_type":    "authorization_code",
    })
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        flash("Failed to get access token from Google.", "error")
        return redirect(url_for("login"))

    # Fetch user profile
    profile = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    email    = profile.get("email", "")
    name     = profile.get("name", email.split("@")[0])
    oauth_id = f"google:{profile.get('id')}"

    user = db.get_or_create_oauth_user(oauth_id=oauth_id, username=name, email=email)
    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    return redirect(url_for("index"))


@app.route("/auth/github")
def oauth_github():
    """Redirect user to GitHub's OAuth consent screen."""
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = {
        "client_id":    os.getenv("GITHUB_CLIENT_ID"),
        "redirect_uri": url_for("oauth_github_callback", _external=True),
        "scope":        "read:user user:email",
        "state":        state,
    }
    from urllib.parse import urlencode
    return redirect("https://github.com/login/oauth/authorize?" + urlencode(params))


@app.route("/auth/github/callback")
def oauth_github_callback():
    """Handle GitHub's redirect back after user consents."""
    error = request.args.get("error")
    if error:
        flash(f"GitHub login cancelled: {error}", "error")
        return redirect(url_for("login"))

    if request.args.get("state") != session.pop("oauth_state", None):
        flash("Invalid OAuth state. Please try again.", "error")
        return redirect(url_for("login"))

    code = request.args.get("code")
    # Exchange code for token
    token_resp = http_requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id":     os.getenv("GITHUB_CLIENT_ID"),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
            "code":          code,
            "redirect_uri":  url_for("oauth_github_callback", _external=True),
        }
    ).json()

    access_token = token_resp.get("access_token")
    if not access_token:
        flash("Failed to get access token from GitHub.", "error")
        return redirect(url_for("login"))

    # Fetch user profile
    profile = http_requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}",
                 "Accept": "application/vnd.github+json"}
    ).json()

    # GitHub may not expose email publicly — fetch separately
    email = profile.get("email") or ""
    if not email:
        emails = http_requests.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}",
                     "Accept": "application/vnd.github+json"}
        ).json()
        primary = next((e["email"] for e in emails if e.get("primary")), None)
        email = primary or ""

    username = profile.get("login", f"gh_{profile.get('id')}")
    oauth_id = f"github:{profile.get('id')}"

    user = db.get_or_create_oauth_user(oauth_id=oauth_id, username=username, email=email)
    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    return redirect(url_for("index"))


# ── Error handlers ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
