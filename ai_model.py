import requests, os, time

HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

EMOTION_MODEL = "bhadresh-savani/distilbert-base-uncased-emotion"
GENERATION_MODEL = "google/flan-t5-small"

def query_hf_model(model_name, payload, retries=3, timeout=60):
    """Handles retries + Hugging Face cold starts safely."""
    for attempt in range(retries):
        try:
            res = requests.post(
                f"https://api-inference.huggingface.co/models/{EMOTION_MODEL}",
                f"https://api-inference.huggingface.co/models/{GENERATION_MODEL}"
                headers=HEADERS,
                json=payload,
                timeout=timeout
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0:
                    return data
                elif isinstance(data, dict) and "error" not in data:
                    return data
            else:
                print(f"⚠️ Attempt {attempt+1}: HF API returned status {res.status_code}")
        except Exception as e:
            print(f"❌ Attempt {attempt+1}: {e}")
        time.sleep(2)  # wait before retry
    return None


def analyze_dream(dream_text):
    payload = {"inputs": dream_text}
    data = query_hf_model(EMOTION_MODEL, payload, retries=3, timeout=40)

    if not data or not isinstance(data, list) or not isinstance(data[0], list):
        print("⚠️ Emotion model returned unexpected response:", data)
        return (
            "Could not analyze dream at the moment. Please try again.",
            {"primary_emotion": "unknown", "secondary_emotion": "unknown"}
        )

    emotions = data[0]
    emotions = sorted(emotions, key=lambda x: x["score"], reverse=True)

    top1, top2 = emotions[0], emotions[1]
    result_text = (
        f"Your dream mainly reflects **{top1['label'].lower()}** "
        f"(confidence: {round(top1['score'], 2)}) "
        f"and hints of **{top2['label'].lower()}** "
        f"(confidence: {round(top2['score'], 2)})."
    )

    analysis = {
        "primary_emotion": top1["label"],
        "secondary_emotion": top2["label"],
        "confidence_primary": round(top1["score"], 2),
        "confidence_secondary": round(top2["score"], 2),
    }
    return result_text, analysis


def interpret_dream(dream_text):
    payload = {"inputs": f"Interpret this dream in a positive, psychological way:\n{dream_text}"}
    data = query_hf_model(GENERATION_MODEL, payload, retries=3, timeout=80)

    try:
        if data and isinstance(data, list):
            return data[0].get("generated_text", "").strip()
        elif isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"].strip()
    except Exception as e:
        print("❌ Interpretation parsing error:", e)

    return "Could not interpret dream at the moment. Please try again."
