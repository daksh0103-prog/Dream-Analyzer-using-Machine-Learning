import requests, os

HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

EMOTION_MODEL = "bhadresh-savani/distilbert-base-uncased-emotion"
GENERATION_MODEL = "google/flan-t5-small"

def analyze_dream(dream_text):
    payload = {"inputs": dream_text}
    res = requests.post(
        f"https://api-inference.huggingface.co/models/{EMOTION_MODEL}",
        headers=HEADERS, json=payload, timeout=30
    )
    data = res.json()[0]
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

def interpret_dream(dream_text):
    payload = {"inputs": f"Interpret this dream positively:\n{dream_text}"}
    res = requests.post(
        f"https://api-inference.huggingface.co/models/{GENERATION_MODEL}",
        headers=HEADERS, json=payload, timeout=60
    )
    text = res.json()[0]["generated_text"]
    return text.strip()
