class KaliteKontrol:
    def __init__(self, minimum_score=90.0):
        self.minimum_score = minimum_score

    def validate(self, word, research, usage, sentences, responses):
        checks = {
            "research_present": bool(research.get("meanings")),
            "usage_present": bool(usage.get("contexts")),
            "sentences_present": bool(sentences),
            "responses_present": bool(responses)
        }
        score = 100.0 if all(checks.values()) else 0.0
        return {
            "accepted": score >= self.minimum_score,
            "score": score,
            "checks": checks
        }
