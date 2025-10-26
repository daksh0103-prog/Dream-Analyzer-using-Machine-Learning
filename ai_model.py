import requests, os

HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

EMOTION_MODEL = "bhadresh-savani/distilbert-base-uncased-emotion"
GENERATION_MODEL = "google/flan-t5-small"


def analyze_dream(dream_text):
    try:
        payload = {"inputs": dream_text}
        res = requests.post(
            f"https://api-inference.huggingface.co/models/{EMOTION_MODEL}",
            headers=HEADERS,
            json=payload,
            timeout=30
        )

        # Check if response is OK
        if res.status_code != 200:
            print("Error in emotion model:", res.text)
            return "Sorry, I couldn’t analyze emotions right now.", None

        data = res.json()
        # Handle model warm-up or empty response
        if not data or isinstance(data, dict) and "error" in data:
            print("Model returned error:", data)
            return "The model is warming up. Try again in a few seconds.", None

        emotions = data[0]
        top = sorted(emotions, key=lambda x: x["score"], reverse=True)
        top1, top2 = top[0], top[1]

        result_text = (
            f"Your dream mainly reflects **{top1['label'].lower()}** "
            f"(confidence: {round(top1['score'], 2)})"
            f", and hints of **{top2['label'].lower()}** "
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
            return "Sorry, I couldn’t interpret the dream right now."

        data = res.json()
        if not data or isinstance(data, dict) and "error" in data:
            print("Model returned error:", data)
            return "The interpretation model is still loading. Try again soon."

        text = data[0].get("generated_text", "").strip()
        if not text:
            return "The model didn’t generate a clear interpretation."

        return text

    except Exception as e:
        print("Error in interpret_dream:", e)
        return "An unexpected error occurred while interpreting your dream."
