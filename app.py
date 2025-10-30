import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from database import MongoDB
from ai_model import DreamAI

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Environment variable checks
MONGO_URI = os.getenv("MONGO_URI")
HF_TOKEN = os.getenv("HF_TOKEN")
INTERPRET_MODEL_NAME = os.getenv("INTERPRET_MODEL_NAME", "google/flan-t5-small")
EMOTION_MODEL_NAME = os.getenv("EMOTION_MODEL_NAME", "j-hartmann/emotion-english-distilroberta-base")

if not all([MONGO_URI, HF_TOKEN, app.secret_key]):
    raise ValueError("Missing required environment variables. Check SECRET_KEY, MONGO_URI, HF_TOKEN.")

# Initialize database and AI model
db = MongoDB(MONGO_URI)
dream_ai = DreamAI(HF_TOKEN, INTERPRET_MODEL_NAME, EMOTION_MODEL_NAME)


# ----------------- AUTH ROUTES -----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if db.get_user(username):
            flash("Username already exists. Try another.", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        db.create_user(username, hashed_pw)
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        user = db.get_user(username)
        if user and check_password_hash(user["password"], password):
            session["user"] = username
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ----------------- MAIN FUNCTIONALITY -----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        dream_text = request.form["dream"].strip()
        if not dream_text:
            flash("Please enter your dream before analyzing.", "warning")
            return redirect(url_for("index"))

        # AI Analysis
        try:
            interpretation = dream_ai.interpret_dream(dream_text)
            emotion = dream_ai.analyze_emotion(dream_text)
        except Exception as e:
            flash(f"Error analyzing dream: {str(e)}", "danger")
            return redirect(url_for("index"))

        # Save to DB
        dream_entry = {
            "user": session["user"],
            "text": dream_text,
            "interpretation": interpretation,
            "emotion": emotion,
            "date": datetime.utcnow(),
        }
        db.save_dream(session["user"], dream_entry)
        db.update_streak(session["user"])
        db.check_achievements(session["user"])

        return render_template("result.html", dream=dream_entry)

    return render_template("index.html")


@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login"))

    dreams = db.get_dreams(session["user"])
    achievements = db.get_achievements(session["user"])
    streak = db.get_streak(session["user"])

    return render_template(
        "history.html",
        dreams=dreams,
        achievements=achievements,
        streak=streak,
    )


# ----------------- EDIT DREAM -----------------
@app.route("/edit_dream/<dream_id>", methods=["GET", "POST"])
def edit_dream(dream_id):
    # Fetch the existing dream from the database
    dream = db.get_dream_by_id(dream_id)
    if not dream:
        flash("Dream not found.", "danger")
        return redirect(url_for("history"))

    if request.method == "POST":
        updated_text = request.form.get("dream_text").strip()

        # Only re-analyze if the text actually changed
        if updated_text != dream.get("dream_text", ""):
            try:
                # Use the existing DreamAI instance for both emotion + interpretation
                emotion = dream_ai.analyze_emotion(updated_text)
                interpretation = dream_ai.interpret_dream(updated_text)
                print(f"✅ Dream re-analyzed: Emotion = {emotion}, Interpretation = {interpretation}")
            except Exception as e:
                print(f"⚠️ Interpretation error: {e}")
                # Fallback to old data if error occurs
                emotion = dream.get("emotion", "Unknown")
                interpretation = dream.get("interpretation", "No interpretation")
        else:
            # Keep the existing emotion & interpretation if text unchanged
            emotion = dream.get("emotion", "Unknown")
            interpretation = dream.get("interpretation", "No interpretation")

        # Preserve the original timestamp unless missing
        updated_data = {
            "dream_text": updated_text,
            "emotion": emotion,
            "interpretation": interpretation,
            "date": dream.get("date", datetime.utcnow())
        }

        # Update the dream in MongoDB
        if db.update_dream(dream_id, updated_data):
            flash("Dream updated successfully!", "success")
        else:
            flash("Dream update failed or no changes detected.", "warning")

        return redirect(url_for("history"))

    # Render the edit page
    return render_template("edit_dream.html", dream=dream)


# ----------------- DELETE DREAM -----------------
@app.route("/delete_dream/<dream_id>", methods=["GET","POST"])
def delete_dream(dream_id):
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        db.delete_dream(dream_id)
        flash("Dream deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting dream: {str(e)}", "danger")

    return redirect(url_for("history"))


@app.route("/api/dreams")
def api_dreams():
    """Optional JSON API route for debugging or frontend use"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    dreams = db.get_dreams(session["user"])
    return jsonify(dreams)


# ----------------- ERROR HANDLERS -----------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ----------------- RUN -----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
