from pymongo import MongoClient

# Replace with your MongoDB Atlas or local connection string
MONGO_URI = "mongodb+srv://daksh0103:daksh0103@cluster0.7ztzqij.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)

# Create or connect to a database and collection
db = client["dream_analyzer_db"]
dreams_collection = db["dreams"]

def save_dream(user, dream_text, analysis):
    dreams_collection.insert_one({
        "user": user,
        "dream": dream_text,   # ✅ correct key name
        "analysis": analysis
    })

    print("Dream saved successfully!")
