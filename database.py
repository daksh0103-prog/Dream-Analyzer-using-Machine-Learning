from pymongo import MongoClient, errors
import os
from bson import ObjectId
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash


MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://daksh0103:daksh0103@cluster0.7ztzqij.mongodb.net/?retryWrites=true&w=majority&ssl=true&tlsAllowInvalidCertificates=true"
)

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # test connection
    print("✅ MongoDB connection successful!")
    
except errors.ServerSelectionTimeoutError as e:
    print("❌ MongoDB connection failed:", e)

db = client["dream_analyzer"]
dreams_collection = db["dreams"]
users_collection = db["users"]

# ---------------- USER AUTH ----------------
def create_user(username, password):
    if users_collection.find_one({"username": username}):
        return False  # user already exists
    hashed_pw = generate_password_hash(password)
    users_collection.insert_one({
        "username": username,
        "password": hashed_pw,
        "streak_count": 0,
        "achievements": []
    })
    return True


def verify_user(username, password):
    user = users_collection.find_one({"username": username})
    if user and check_password_hash(user["password"], password):
        return user
    return None

# ---------------- STREAK SYSTEM ----------------
def update_streak(user_id):
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    today = datetime.now()  # ✅ Use full datetime, not .date()

    if not user or "last_entry_date" not in user:
        # First dream ever or no streak data
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"streak_count": 1, "last_entry_date": today}}
        )
    else:
        last_date = user["last_entry_date"]
        streak = user.get("streak_count", 0)

        # Convert to date objects for comparison
        last_day = last_date.date() if isinstance(last_date, datetime) else last_date
        today_day = today.date()

        if today_day == last_day:
            # Same day → no change
            return
        elif today_day - last_day == timedelta(days=1):
            # Consecutive day → increase streak
            streak += 1
        else:
            # Missed a day → reset streak
            streak = 1

        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"streak_count": streak, "last_entry_date": today}}
        )

# ---------------- ACHIEVEMENTS ----------------
def check_achievements(user_id):
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    streak = user.get("streak_count", 0)
    total_dreams = dreams_collection.count_documents({"user_id": ObjectId(user_id)})

    achievements = []

    if streak >= 7:
        achievements.append("🌙 7-Day Dream Streak")
    if streak >= 30:
        achievements.append("🌕 30-Day Dream Streak")
    if total_dreams >= 10:
        achievements.append("💭 Dream Explorer")
    if total_dreams >= 50:
        achievements.append("🧠 Dream Master")

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"achievements": achievements}}
    )

# ---------------- DREAM SAVE ----------------
def save_dream(user_id, dream_text, analysis, interpretation):
    dream_entry = {
        "user_id": ObjectId(user_id),
        "dream": dream_text,
        "analysis": analysis,
        "interpretation": interpretation,
        "timestamp": datetime.now().strftime("%d %b %Y, %I:%M %p")
    }
    dreams_collection.insert_one(dream_entry)
    print("Dream saved successfully!")

    # Update streak & achievements
    update_streak(user_id)
    check_achievements(user_id)
