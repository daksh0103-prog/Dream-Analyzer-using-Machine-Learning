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
            headers=HEADERS, json=payload, timeout=30
        )
        res.raise_for_status()  # Raise exception for HTTP errors
        data = res.json()

        # Check if API returned an error
        if isinstance(data, dict) and data.get("error"):
            raise ValueError(data["error"])

        data = data[0]
        top = sorted(data, key=lambda x: x["score"], reverse=True)
        top1, top2 = top[0], top[1]

        result_text = f"Your dream mainly reflects **{top1['label'].lower()}** (confidence: {round(top1['score'], 2)})"
        result_text += f", and hints of **{top2['label'].lower()}** (confidence: {round(top2['score'], 2)})."

        analysis = {
            "primary_emotion": top1["label"],
            "secondary_emotion": top2["label"],
            "confidence_primary": round(top1["score"], 2),
            "confidence_secondary": round(top2["score"], 2)
        }
        return result_text, analysis

    except Exception as e:
        print("❌ Error in analyze_dream:", e)
        return "Could not analyze dream at the moment.", {"primary_emotion": "neutral", "secondary_emotion": "neutral"}


def interpret_dream(dream_text):
    try:
        payload = {"inputs": f"Interpret this dream positively:\n{dream_text}"}
        res = requests.post(
            f"https://api-inference.huggingface.co/models/{GENERATION_MODEL}",
            headers=HEADERS, json=payload, timeout=60
        )
        res.raise_for_status()
        data = res.json()

        if isinstance(data, dict) and data.get("error"):
            raise ValueError(data["error"])

        text = data[0].get("generated_text", "")
        return text.strip() if text else "Could not generate interpretation at the moment."

    except Exception as e:
        print("❌ Error in interpret_dream:", e)
        return "Could not interpret dream at the moment."

