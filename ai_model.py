import requests
import os

# Get Hugging Face token from environment
HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# Models
EMOTION_MODEL = "bhadresh-savani/distilbert-base-uncased-emotion"
GENERATION_MODEL = "sshleifer/tiny-flan-t5"


def analyze_dream(dream_text):
    """
    Analyze emotions in a dream using distilbert-base-uncased-emotion
    Returns:
        result_text: human-readable string
        analysis: dict with primary and secondary emotions and confidence
    """
    try:
        payload = {"inputs": dream_text}
        res = requests.post(
            f"https://api-inference.huggingface.co/models/{EMOTION_MODEL}",
            headers=HEADERS,
            json=payload,
            timeout=30
        )

        if res.status_code != 200:
            print("Error in emotion model:", res.text)
            return "Sorry, I couldn’t analyze emotions right now.", None

        data = res.json()
        if not data or (isinstance(data, dict) and "error" in data):
            print("Model returned error:", data)
            return "The model is warming up. Try again shortly.", None

        # Sort emotions by score
        top = sorted(data[0], key=lambda x: x["score"], reverse=True)
        top1, top2 = top[0], top[1]

        result_text = (
            f"Your dream mainly reflects **{top1['label'].lower()}** "
            f"(confidence: {round(top1['score'], 2)}), "
            f"and hints of **{top2['label'].lower()}** "
            f"(confidence: {round(top2['score'], 2)})."
        )

        analysis = {
            "primary_emotion": top1["label"],
            "secondary_emotion": top2["label"],
            "confidence_primary": round(top1["score"], 2),
            "confidence_secondary": round(top2["score"], 2)
        }

        return result_text, analysis

    except Exception as e:
        print("Error in analyze_dream:", e)
        return "Sorry, an unexpected error occurred while analyzing.", None


def interpret_dream(dream_text):
    """
    Interpret a dream positively using tiny-flan-t5
    Returns a string of interpretation, or a fallback message if it fails
    """
    try:
        payload = {"inputs": f"Interpret this dream positively:\n{dream_text}"}
        res = requests.post(
            f"https://api-inference.huggingface.co/models/{GENERATION_MODEL}",
            headers=HEADERS,
            json=payload,
            timeout=60
        )

        if res.status_code != 200:
            print("Error in interpretation model:", res.text)
            return "Interpretation not available"

        data = res.json()
        if not data or (isinstance(data, dict) and "error" in data):
            print("Model returned error:", data)
            return "Interpretation not available"

        text = data[0].get("generated_text", "").strip()
        if not text:
            return "Interpretation not available"

        return text

    except Exception as e:
        print("Error in interpret_dream:", e)
        return "Interpretation not available"
