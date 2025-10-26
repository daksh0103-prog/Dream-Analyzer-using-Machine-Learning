from flask import Flask, render_template, request, url_for, flash, redirect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from ai_model import analyze_dream, interpret_dream
from database import create_user, verify_user, users_collection, save_dream, dreams_collection
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "f9d8e7c6b5a4d3f2e1c0b9a8f7d6e5c4b3a2d1f0e9c8b7a6d5f4c3b2a1e0f9d8"  # replace with a secure secret in production

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# -------------------------------
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.username = user_data.get("username", "Unknown")


@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = users_collection.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception:
        app.logger.exception("Failed loading user")
    return None


# -------------------------------
@app.route('/')
@login_required
def home():
    return render_template('index.html')


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    dream_text = request.form.get("dream", "").strip()
    if not dream_text:
        return render_template("index.html", result="Please enter a dream!")

    try:
        # Step 1: Emotion analysis
        result_text, analysis = analyze_dream(dream_text)

        # Step 2: Dream interpretation (local)
        interpretation = interpret_dream(dream_text)
        if not interpretation:
            interpretation = "Interpretation not available"

        # Step 3: Save to DB
        if current_user.is_authenticated:
            try:
                save_dream(current_user.id, dream_text, analysis, interpretation)
            except Exception:
                app.logger.exception("Failed saving dream")

        return render_template(
            "index.html",
            dream=dream_text,
            result=result_text,
            interpretation=interpretation
        )

    except Exception:
        app.logger.exception("Error in /analyze route")
        return render_template(
            "index.html",
            result="An error occurred while analyzing your dream."
        )


@app.route('/history')
@login_required
def history():
    try:
        dreams = list(dreams_collection.find({"user_id": current_user.id}).sort([('_id', -1)]))
    except Exception:
        app.logger.exception("Failed fetching history")
        dreams = []
    return render_template('history.html', dreams=dreams)


# ----------------------------
# User authentication routes
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
                flash('Account created! Log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Username exists!', 'danger')
        except Exception:
            app.logger.exception("Failed creating user")
            flash('Server error. Try later.', 'danger')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Enter username and password', 'danger')
            return render_template('login.html')
        try:
            user = verify_user(username, password)
            if user:
                login_user(User(user))
                flash(f'Welcome back, {username}!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid credentials', 'danger')
        except Exception:
            app.logger.exception("Login check failed")
            flash('Server error. Try later.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))


# ----------------------------
# Edit & Delete dreams
# ----------------------------
@app.route('/edit/<dream_id>', methods=['GET', 'POST'])
@login_required
def edit_dream(dream_id):
    try:
        dream = dreams_collection.find_one({"_id": ObjectId(dream_id), "user_id": current_user.id})
    except Exception:
        app.logger.exception("Failed fetching dream")
        flash("Server error.", "danger")
        return redirect(url_for('history'))

    if not dream:
        flash("Dream not found", "danger")
        return redirect(url_for('history'))

    if request.method == 'POST':
        updated_dream = request.form.get('dream', '').strip()
        try:
            dreams_collection.update_one({"_id": ObjectId(dream_id)}, {"$set": {"dream": updated_dream}})
            flash("Dream updated successfully", "success")
        except Exception:
            app.logger.exception("Failed updating dream")
            flash("Update failed", "danger")
        return redirect(url_for('history'))

    return render_template('edit_dream.html', dream=dream)


@app.route('/delete/<dream_id>')
@login_required
def delete_dream(dream_id):
    try:
        result = dreams_collection.delete_one({"_id": ObjectId(dream_id), "user_id": current_user.id})
        if result.deleted_count:
            flash("Dream deleted", "success")
        else:
            flash("Dream not found or permission denied", "danger")
    except Exception:
        app.logger.exception("Failed deleting dream")
        flash("Server error", "danger")
    return redirect(url_for('history'))


# ----------------------------
if __name__ == '__main__':
    # Use gunicorn for production on Render
    app.run(debug=True, host='0.0.0.0', port=5000)
