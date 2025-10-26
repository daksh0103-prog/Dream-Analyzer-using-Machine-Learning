from transformers import pipeline

# Lazy model loaders — created only when called
emotion_analyzer = None
dream_interpreter = None

def get_emotion_analyzer():
    global emotion_analyzer
    if emotion_analyzer is None:
        emotion_analyzer = pipeline(
            "text-classification",
            model="bhadresh-savani/distilbert-base-uncased-emotion",  # lighter alternative (~180 MB)
            return_all_scores=True,
            framework="pt"
        )
    return emotion_analyzer


def get_dream_interpreter():
    global dream_interpreter
    if dream_interpreter is None:
        # extremely lightweight text generator
        dream_interpreter = pipeline(
            "text-generation",
            model="hf-internal-testing/tiny-random-gpt2",  # placeholder under 100 MB
            max_new_tokens=80
        )
    return dream_interpreter


def analyze_dream(dream_text):
    """
    Analyze the dream and extract top emotional insights.
    """
    analyzer = get_emotion_analyzer()
    results = analyzer(dream_text)[0]

    # Sort emotions by confidence
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)

    top1 = sorted_results[0]
    top2 = sorted_results[1] if len(sorted_results) > 1 else None

    result_text = f"Your dream mainly reflects **{top1['label'].lower()}** (confidence: {round(top1['score'], 2)})"
    if top2:
        result_text += f", and also hints of **{top2['label'].lower()}** (confidence: {round(top2['score'], 2)})."

    analysis = {
        "primary_emotion": top1["label"],
        "secondary_emotion": top2["label"] if top2 else None,
        "confidence_primary": round(top1["score"], 2),
        "confidence_secondary": round(top2["score"], 2) if top2 else None
    }

    return result_text, analysis


def interpret_dream(dream_text):
    """
    Generate symbolic interpretation or meaning of a dream.
    """
    generator = get_dream_interpreter()
    prompt = f"""
    You are a dream analyst. Interpret this dream briefly and positively:
    Dream: "{dream_text}"
    """
    result = generator(prompt)[0]["generated_text"]
    return result.strip()
