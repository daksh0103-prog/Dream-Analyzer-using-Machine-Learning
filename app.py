from flask import Flask, render_template, request, url_for, jsonify, session, flash, redirect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from ai_model import analyze_dream, interpret_dream  # AI model functions
from database import create_user, verify_user, users_collection, save_dream, dreams_collection
from datetime import datetime
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# -------------------------------
# Flask-Login User Management
# -------------------------------
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.username = user_data["username"]

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
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
        # Run AI Analysis safely
        result_text, analysis = analyze_dream(dream_text)
        interpretation = interpret_dream(dream_text)

        # Save to DB
        if current_user.is_authenticated:
            save_dream(current_user.id, dream_text, analysis, interpretation)

        return render_template(
            "index.html",
            dream=dream_text,
            result=result_text,
            interpretation=interpretation
        )

    except Exception as e:
        # Print full traceback in logs
        import traceback
        print("❌ Error in /analyze route:", e)
        traceback.print_exc()

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
    dreams = list(dreams_collection.find({"user_id": current_user.id}).sort([('_id', -1)]))
    return render_template('history.html', dreams=dreams)


# ----------------------------
# Chart Data Route
# ----------------------------
@app.route('/chart-data')
def chart_data():
    dreams = list(dreams_collection.find())
    emotion_counts = {}

    for dream in dreams:
        # Safe access: skip dreams without analysis or primary_emotion
        primary_emotion = dream.get('analysis', {}).get('primary_emotion', 'neutral')
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
    dreams = list(dreams_collection.find())
    if not dreams:
        return render_template(
            'personality.html',
            summary="No dreams analyzed yet. Analyze a few to discover your dream personality!"
        )

    # Count primary emotions safely
    emotion_counts = {}
    for dream in dreams:
        primary_emotion = dream.get('analysis', {}).get('primary_emotion', 'neutral')
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
        username = request.form['username']
        password = request.form['password']
        if create_user(username, password):
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists!', 'danger')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = verify_user(username, password)
        if user:
            login_user(User(user))
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!', 'danger')
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
    dream = dreams_collection.find_one({"_id": ObjectId(dream_id), "user_id": current_user.id})
    if not dream:
        flash("Dream not found or access denied!", "danger")
        return redirect(url_for('history'))

    if request.method == 'POST':
        updated_dream = request.form['dream']
        dreams_collection.update_one(
            {"_id": ObjectId(dream_id)},
            {"$set": {"dream": updated_dream}}
        )
        flash("Dream updated successfully!", "success")
        return redirect(url_for('history'))

    return render_template('edit_dream.html', dream=dream)


# ----------------------------
# Delete Dream
# ----------------------------
@app.route('/delete/<dream_id>')
@login_required
def delete_dream(dream_id):
    result = dreams_collection.delete_one({"_id": ObjectId(dream_id), "user_id": current_user.id})
    if result.deleted_count:
        flash("Dream deleted successfully!", "success")
    else:
        flash("Dream not found or you don't have permission.", "danger")
    return redirect(url_for('history'))


# ----------------------------
# Run Flask
# ----------------------------
if __name__ == '__main__':
    app.run(debug=True)
