from flask import Flask, render_template, request, url_for, jsonify, session, flash, redirect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from ai_model import analyze_dream, interpret_dream  # AI model functions
from database import create_user, verify_user, users_collection, save_dream, dreams_collection
from datetime import datetime
from bson import ObjectId
import traceback

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # <-- replace with a secure secret in production

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# -------------------------------
# Flask-Login User Management
# -------------------------------
class User(UserMixin):
    def __init__(self, user_data):
        # Expect user_data to be a dict-like MongoDB document
        self.id = str(user_data["_id"])
        self.username = user_data.get("username", "Unknown")


@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = users_collection.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception:
        app.logger.exception("Failed loading user from DB")
    return None


# -------------------------------
# Routes
# -------------------------------
@app.route('/')
@login_required
def home():
    return render_template('index.html')


# ----------------------------
# Analyze Dream Route
# ----------------------------
@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    dream_text = request.form.get("dream", "").strip()
    if not dream_text:
        return render_template("index.html", result="Please enter a dream!")

    try:
        # Run AI Analysis safely (ai_model should itself be robust)
        result_text, analysis = analyze_dream(dream_text)
        interpretation = interpret_dream(dream_text)

        # Save to DB (guard DB call with try/except to avoid crashing the route)
        if current_user.is_authenticated:
            try:
                # save_dream should accept (user_id, dream_text, analysis, interpretation)
                save_dream(current_user.id, dream_text, analysis, interpretation)
            except Exception:
                app.logger.exception("Failed to save dream; continuing without failing the request")

        return render_template(
            "index.html",
            dream=dream_text,
            result=result_text,
            interpretation=interpretation
        )

    except Exception as e:
        # ensure we never return None — always render a template
        app.logger.exception("Error in /analyze route")
        return render_template(
            "index.html",
            result="An error occurred while analyzing your dream. Please try again later."
        )


# ----------------------------
# History Route
# ----------------------------
@app.route('/history')
@login_required
def history():
    try:
        dreams = list(dreams_collection.find({"user_id": current_user.id}).sort([('_id', -1)]))
    except Exception:
        app.logger.exception("Failed fetching history; returning empty list")
        dreams = []
    return render_template('history.html', dreams=dreams)


# ----------------------------
# Chart Data Route
# ----------------------------
@app.route('/chart-data')
def chart_data():
    try:
        dreams = list(dreams_collection.find())
    except Exception:
        app.logger.exception("Failed fetching dreams for chart")
        return jsonify({})

    emotion_counts = {}
    for dream in dreams:
        # safe access: guard missing fields and different data shapes
        analysis = dream.get('analysis') if isinstance(dream, dict) else None
        primary_emotion = (analysis or {}).get('primary_emotion', 'neutral')
        emotion_counts[primary_emotion] = emotion_counts.get(primary_emotion, 0) + 1

    return jsonify(emotion_counts)


# ----------------------------
# Analytics Route
# ----------------------------
@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')


# ----------------------------
# Personality Route
# ----------------------------
@app.route('/personality')
@login_required
def personality():
    try:
        dreams = list(dreams_collection.find())
    except Exception:
        app.logger.exception("Failed fetching dreams for personality")
        return render_template('personality.html', summary="Could not load personality data right now.")

    if not dreams:
        return render_template(
            'personality.html',
            summary="No dreams analyzed yet. Analyze a few to discover your dream personality!"
        )

    # Count primary emotions safely
    emotion_counts = {}
    for dream in dreams:
        analysis = dream.get('analysis') if isinstance(dream, dict) else None
        primary_emotion = (analysis or {}).get('primary_emotion', 'neutral')
        emotion_counts[primary_emotion] = emotion_counts.get(primary_emotion, 0) + 1

    dominant_emotion = max(emotion_counts, key=emotion_counts.get)

    emotion_to_personality = {
        "joy": "You appear to be a positive and optimistic thinker who often finds light even in difficult times.",
        "sadness": "You seem emotionally deep and reflective, often processing unresolved feelings through your dreams.",
        "fear": "You might be anxious or cautious, frequently dreaming about uncertainty or loss of control.",
        "anger": "You may be passionate and strong-willed, often facing inner conflicts in your subconscious.",
        "disgust": "You could be highly self-aware and selective, possibly dealing with stress or avoidance in waking life.",
        "surprise": "You are curious and open-minded, adapting well to unexpected events.",
        "neutral": "You seem emotionally balanced and introspective, with dreams that reflect mental stability."
    }

    summary = emotion_to_personality.get(dominant_emotion, "Your dreams reflect a balanced and diverse emotional state.")

    return render_template('personality.html', summary=summary, emotion_counts=emotion_counts)


# ----------------------------
# User Auth Routes
# ----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Please provide username and password', 'danger')
            return render_template('register.html')

        try:
            if create_user(username, password):
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Username already exists!', 'danger')
        except Exception:
            app.logger.exception("Failed creating user")
            flash('Server error. Please try again later.', 'danger')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Please enter username and password', 'danger')
            return render_template('login.html')

        try:
            user = verify_user(username, password)
            if user:
                login_user(User(user))
                flash(f'Welcome back, {username}!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password!', 'danger')
        except Exception:
            app.logger.exception("Login check failed")
            flash('Server error. Please try again later.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ----------------------------
# Edit Dream
# ----------------------------
@app.route('/edit/<dream_id>', methods=['GET', 'POST'])
@login_required
def edit_dream(dream_id):
    try:
        dream = dreams_collection.find_one({"_id": ObjectId(dream_id), "user_id": current_user.id})
    except Exception:
        app.logger.exception("Failed fetching dream for edit")
        flash("Server error. Please try again later.", "danger")
        return redirect(url_for('history'))

    if not dream:
        flash("Dream not found or access denied!", "danger")
        return redirect(url_for('history'))

    if request.method == 'POST':
        updated_dream = request.form.get('dream', '').strip()
        try:
            dreams_collection.update_one(
                {"_id": ObjectId(dream_id)},
                {"$set": {"dream": updated_dream}}
            )
            flash("Dream updated successfully!", "success")
        except Exception:
            app.logger.exception("Failed updating dream")
            flash("Failed to update dream. Please try again.", "danger")
        return redirect(url_for('history'))

    return render_template('edit_dream.html', dream=dream)


# ----------------------------
# Delete Dream
# ----------------------------
@app.route('/delete/<dream_id>')
@login_required
def delete_dream(dream_id):
    try:
        result = dreams_collection.delete_one({"_id": ObjectId(dream_id), "user_id": current_user.id})
        if result.deleted_count:
            flash("Dream deleted successfully!", "success")
        else:
            flash("Dream not found or you don't have permission.", "danger")
    except Exception:
        app.logger.exception("Failed deleting dream")
        flash("Server error. Please try again later.", "danger")
    return redirect(url_for('history'))


# ----------------------------
# Run Flask (development only)
# ----------------------------
if __name__ == '__main__':
    # For production on Render use gunicorn (see deployment notes below)
    app.run(debug=True, host='0.0.0.0', port=5000)
