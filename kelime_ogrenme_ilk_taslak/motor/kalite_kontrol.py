from __future__ import annotations


class KaliteKontrol:
    def __init__(self, minimum_score=90.0):
        self.minimum_score = minimum_score

    def validate(self, word, research, usage, sentences, responses):
        valid_sentences = [
            item for item in (sentences or [])
            if isinstance(item, dict)
            and isinstance(item.get("sentence"), str)
            and len(item["sentence"].strip()) >= 12
            and word.casefold() in item["sentence"].casefold()
        ]
        sentence_sources = {
            item.get("source") for item in valid_sentences if item.get("source")
        }
        senses = research.get("senses", []) if isinstance(research, dict) else []

        checks = {
            "word_valid": bool(word and word.strip()),
            "research_present": len(research.get("meanings", [])) >= 2,
            "distinct_senses": len(senses) >= 2,
            "sources_present": len(research.get("sources", [])) >= 2,
            "usage_present": len(usage.get("contexts", [])) >= 2,
            "sentences_present": len(valid_sentences) >= 3,
            "sentence_sources": len(sentence_sources) >= 1,
            "responses_present": len(responses) >= 2,
        }
        passed = sum(checks.values())
        score = round((passed / len(checks)) * 100, 1)
        return {
            "accepted": score >= self.minimum_score,
            "score": score,
            "checks": checks,
            "required_score": self.minimum_score,
        }
