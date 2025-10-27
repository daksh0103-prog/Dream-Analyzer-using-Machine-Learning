from pymongo import MongoClient, errors
from bson import ObjectId
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash


class MongoDB:
    def __init__(self, uri):
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ping")
            print("✅ MongoDB connection successful!")
        except errors.ServerSelectionTimeoutError as e:
            print("❌ MongoDB connection failed:", e)
            raise

        self.db = self.client["dream_analyzer"]
        self.users = self.db["users"]
        self.dreams = self.db["dreams"]

    # ---------------- USER MANAGEMENT ----------------
    def create_user(self, username, password):
        if self.users.find_one({"username": username}):
            return False
        hashed_pw = generate_password_hash(password)
        self.users.insert_one({
            "username": username,
            "password": hashed_pw,
            "streak_count": 0,
            "achievements": []
        })
        return True

    def get_user(self, username):
        return self.users.find_one({"username": username})

    # ---------------- DREAM MANAGEMENT ----------------
    def save_dream(self, username, dream_entry):
        user = self.get_user(username)
        if not user:
            raise ValueError("User not found.")

        dream_entry["user_id"] = user["_id"]
        self.dreams.insert_one(dream_entry)

        # Update streak + achievements
        self.update_streak(user["_id"])
        self.check_achievements(user["_id"])
        print("🌙 Dream saved successfully!")

    def get_dreams(self, username):
        user = self.get_user(username)
        if not user:
            return []
        return list(self.dreams.find({"user_id": user["_id"]}).sort("date", -1))

    # ---------------- STREAK SYSTEM ----------------
    def update_streak(self, user_id):
        user_oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
        user = self.users.find_one({"_id": user_oid})
        today = datetime.now()

        if not user or "last_entry_date" not in user:
            self.users.update_one(
                {"_id": user_oid},
                {"$set": {"streak_count": 1, "last_entry_date": today}},
                upsert=True
            )
            return

        last_date = user.get("last_entry_date")
        streak = user.get("streak_count", 0)

        last_day = last_date.date() if isinstance(last_date, datetime) else last_date
        today_day = today.date()

        if today_day == last_day:
            return
        elif (today_day - last_day) == timedelta(days=1):
            streak += 1
        else:
            streak = 1

        self.users.update_one(
            {"_id": user_oid},
            {"$set": {"streak_count": streak, "last_entry_date": today}}
        )

    def get_streak(self, username):
        user = self.get_user(username)
        return user.get("streak_count", 0) if user else 0

    # ---------------- ACHIEVEMENTS ----------------
    def check_achievements(self, user_id):
        user_oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
        user = self.users.find_one({"_id": user_oid})
        streak = user.get("streak_count", 0)
        total_dreams = self.dreams.count_documents({"user_id": user_oid})

        achievements = []
        if streak >= 7:
            achievements.append("🌙 7-Day Dream Streak")
        if streak >= 30:
            achievements.append("🌕 30-Day Dream Streak")
        if total_dreams >= 10:
            achievements.append("💭 Dream Explorer")
        if total_dreams >= 50:
            achievements.append("🧠 Dream Master")

        self.users.update_one(
            {"_id": user_oid},
            {"$set": {"achievements": achievements}}
        )

    def get_achievements(self, username):
        user = self.get_user(username)
        return user.get("achievements", []) if user else []

    def get_dream_by_id(self, dream_id):
        try:
          return self.dreams_collection.find_one({"_id": ObjectId(dream_id)})
        except Exception:
          return None


    def update_dream(self, dream_id, updated_data):
       self.dreams_collection.update_one(
        {"_id": ObjectId(dream_id)},
        {"$set": updated_data}
    )


   def delete_dream(self, dream_id):
      self.dreams_collection.delete_one({"_id": ObjectId(dream_id)})

