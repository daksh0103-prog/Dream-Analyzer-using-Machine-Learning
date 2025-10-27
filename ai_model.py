import os
import requests

class DreamAI:
    """Handles dream interpretation and emotion analysis using Hugging Face APIs."""

    def __init__(self, hf_token, interpret_model_name, emotion_model_name):
        self.hf_token = hf_token
        self.headers = {"Authorization": f"Bearer {self.hf_token}"} if hf_token else {}
        self.interpret_model = interpret_model_name
        self.emotion_model = emotion_model_name

    # ---------------- DREAM INTERPRETATION ----------------
    def interpret_dream(self, dream_text):
        """Generate an interpretation using the Hugging Face Inference API."""
        try:
            payload = {"inputs": f"Interpret this dream in a positive and meaningful way: {dream_text}"}
            res = requests.post(
                f"https://api-inference.huggingface.co/models/{self.interpret_model}",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            res.raise_for_status()
            data = res.json()

            if isinstance(data, list) and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            elif isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"].strip()
            else:
                return "No clear interpretation available."
        except Exception as e:
            print("Interpretation error:", e)
            return "Sorry, I couldn’t interpret your dream right now."

    # ---------------- EMOTION ANALYSIS ----------------
    def analyze_emotion(self, dream_text):
        """Analyze the emotional tone of the dream."""
        try:
            payload = {"inputs": dream_text}
            res = requests.post(
                f"https://api-inference.huggingface.co/models/{self.emotion_model}",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            res.raise_for_status()
            data = res.json()

            if not isinstance(data, list) or not data or not isinstance(data[0], list):
                return "Unknown"

            top = sorted(data[0], key=lambda x: x["score"], reverse=True)
            top1 = top[0]
            top2 = top[1] if len(top) > 1 else top[0]

            return (
                f"Your dream mainly reflects **{top1['label'].lower()}** "
                f"(confidence: {round(top1['score'], 2)}), "
                f"with hints of **{top2['label'].lower()}** "
                f"(confidence: {round(top2['score'], 2)})."
            )
        except Exception as e:
            print("Emotion analysis error:", e)
            return "Sorry, I couldn’t analyze the emotions right now."
