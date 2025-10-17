from transformers import pipeline

# Load the detailed emotion model
analyzer = pipeline(
    "text-classification",
    model="j-hartmann/emotion-english-distilroberta-base",
    return_all_scores=True,
    framework="pt"
)

def analyze_dream(dream_text):
    """
    Analyze the dream and extract top emotional insights.
    """
    results = analyzer(dream_text)[0]  # Returns list of emotions with scores

    # Sort emotions by confidence
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)

    # Pick top 2 emotions
    top1 = sorted_results[0]
    top2 = sorted_results[1] if len(sorted_results) > 1 else None

    # Build the text response
    result_text = f"Your dream mainly reflects **{top1['label'].lower()}** (confidence: {round(top1['score'], 2)})"
    if top2:
        result_text += f", and also hints of **{top2['label'].lower()}** (confidence: {round(top2['score'], 2)})."

    # Create structured analysis data
    analysis = {
        "primary_emotion": top1["label"],
        "secondary_emotion": top2["label"] if top2 else None,
        "confidence_primary": round(top1["score"], 2),
        "confidence_secondary": round(top2["score"], 2) if top2 else None
    }

    return result_text, analysis
