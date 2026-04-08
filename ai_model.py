import os
import requests


class DreamAI:
    HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
    HF_CLASS_URL = "https://router.huggingface.co/hf-inference/models/SamLowe/roberta-base-go_emotions"

    def __init__(self):
        self.token = os.getenv("HF_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def interpret(self, dream_text: str) -> str:
        try:
            res = requests.post(
                self.HF_CHAT_URL,
                headers=self.headers,
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are Somnia, a wise and mystical dream analyst. Interpret dreams with psychological depth, emotional insight, and symbolic meaning. Be thoughtful, poetic, and positive. Always respond in 2-3 sentences only."
                        },
                        {
                            "role": "user",
                            "content": f"Interpret this dream: {dream_text}"
                        }
                    ],
                    "max_tokens": 200,
                    "temperature": 0.7
                },
                timeout=60,
            )
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print("Interpretation error:", e)
            return "Unable to interpret this dream right now. Please try again."

    def analyze_emotion(self, dream_text: str) -> dict:
        fallback = {
            "primary": "neutral", "secondary": "neutral",
            "confidence_primary": 0.0, "confidence_secondary": 0.0,
            "all": []
        }
        try:
            res = requests.post(
                self.HF_CLASS_URL,
                headers=self.headers,
                json={"inputs": dream_text},
                timeout=60,
            )
            res.raise_for_status()
            data = res.json()

            if not isinstance(data, list) or not data:
                return fallback
            items = data[0] if isinstance(data[0], list) else data
            items = sorted(items, key=lambda x: x["score"], reverse=True)

            return {
                "primary": items[0]["label"].lower(),
                "secondary": items[1]["label"].lower() if len(items) > 1 else items[0]["label"].lower(),
                "confidence_primary": round(items[0]["score"], 2),
                "confidence_secondary": round(items[1]["score"], 2) if len(items) > 1 else 0.0,
                "all": items[:6],
            }
        except Exception as e:
            print("Emotion error:", e)
            return fallback