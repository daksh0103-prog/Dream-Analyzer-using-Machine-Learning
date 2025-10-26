import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import requests
import os

# -------------------------------
# Hugging Face token (for emotion API)
HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# Emotion analysis model (still via HF API)
EMOTION_MODEL = "bhadresh-savani/distilbert-base-uncased-emotion"

# Local dream interpretation model
INTERPRET_MODEL_NAME = "sshleifer/tiny-flan-t5"

# Load tokenizer and model once at startup
tokenizer_interp = AutoTokenizer.from_pretrained(INTERPRET_MODEL_NAME)
model_interp = AutoModelForSeq2SeqLM.from_pretrained(INTERPRET_MODEL_NAME)
# Use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
model_interp.to(device)
# -------------------------------

# -------------------------------
def analyze_dream(dream_text):
    """
    Analyze emotions in a dream using distilbert-base-uncased-emotion.
    Returns a human-readable result and a dict of primary and secondary emotions.
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

        top = sorted(data[0], key=lambda x: x["score"], reverse=True)
        top1, top2 = top[0], top[1]

        result_text = (
            f"Your dream mainly reflects **{top1['label'].lower()}** "
            f"(confidence: {round(top1['score'],2)}), "
            f"and hints of **{top2['label'].lower()}** "
            f"(confidence: {round(top2['score'],2)})."
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

# -------------------------------
def interpret_dream(dream_text):
    """
    Interpret dream using local tiny-flan-t5 model.
    Returns interpretation text, or fallback if generation fails.
    """
    try:
        inputs = tokenizer_interp(
            f"Interpret this dream positively:\n{dream_text}",
            return_tensors="pt"
        ).to(device)

        outputs = model_interp.generate(**inputs, max_length=200)
        text = tokenizer_interp.decode(outputs[0], skip_special_tokens=True)

        return text or "Interpretation not available"

    except Exception as e:
        print("Error in interpret_dream:", e)
        return "Interpretation not available"
