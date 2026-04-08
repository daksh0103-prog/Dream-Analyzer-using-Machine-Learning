import os
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from dotenv import load_dotenv
from datetime import datetime
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

        dream_id = db.save_dream(
            user_id=session["user_id"],
            text=dream_text,
            interpretation=interpretation,
            emotion_primary=emotion["primary"],
            emotion_secondary=emotion["secondary"],
            confidence_primary=emotion["confidence_primary"],
            confidence_secondary=emotion["confidence_secondary"],
        )
        result = {
            "id": dream_id,
            "text": dream_text,
            "interpretation": interpretation,
            "emotion": emotion,
        }
    return render_template("index.html", result=result)


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
        db.update_dream(
            dream_id, session["user_id"], text, interpretation,
            emotion["primary"], emotion["secondary"],
            emotion["confidence_primary"], emotion["confidence_secondary"],
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

    return render_template(
        "analytics.html",
        dreams=dreams,
        emotion_counts=emotion_counts,
        streak=streak,
        total=total,
        personality_title=personality_title,
        personality_desc=personality_desc,
        dominant_emotion=dominant,
    )


# ── Error handlers ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)