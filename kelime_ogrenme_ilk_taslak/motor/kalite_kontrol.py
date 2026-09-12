from __future__ import annotations

import re


class KaliteKontrol:
    def __init__(self, minimum_score=90.0):
        self.minimum_score = float(minimum_score)

    @staticmethod
    def _contains_word(word, text):
        escaped = re.escape(str(word or "").strip())
        if not escaped:
            return False
        return re.search(
            rf"(?<![\wçğıöşüÇĞİÖŞÜ]){escaped}(?![\wçğıöşüÇĞİÖŞÜ])",
            str(text),
            flags=re.IGNORECASE,
        ) is not None

    @staticmethod
    def _distinct(values):
        seen = set()
        for value in values:
            if isinstance(value, dict):
                value = value.get("definition") or value.get("text") or value.get("sentence") or ""
            key = " ".join(str(value).casefold().split())
            if key:
                seen.add(key)
        return len(seen)

    def validate(self, word, research, usage, sentences, responses):
        research = research if isinstance(research, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        sentences = sentences if isinstance(sentences, list) else []
        responses = responses if isinstance(responses, list) else []

        valid_sentences = []
        for item in sentences:
            if not isinstance(item, dict):
                continue
            sentence = str(item.get("sentence") or "").strip()
            source_url = str(item.get("url") or "").strip()
            source = str(item.get("source") or "").strip()
            if len(sentence) < 12 or len(sentence.split()) < 3:
                continue
            if not self._contains_word(word, sentence):
                continue
            if not source_url:
                continue
            valid_sentences.append(item)

        sentence_sources = {
            str(item.get("source") or "").strip()
            for item in valid_sentences
            if item.get("source")
        }
        sentence_urls = {
            str(item.get("url") or "").strip()
            for item in valid_sentences
            if item.get("url")
        }
        senses = research.get("senses", []) or []
        meanings = research.get("meanings", []) or []
        sources = research.get("sources", []) or []
        contexts = usage.get("contexts", []) or []

        checks = {
            "word_valid": bool(str(word or "").strip()),
            "research_present": len(meanings) >= 2,
            "distinct_senses": self._distinct(senses) >= 2,
            "sources_present": len(sources) >= 2,
            "usage_present": len(contexts) >= 2,
            "sentences_present": len(valid_sentences) >= 3,
            "sentence_sources": bool(sentence_sources),
            "sentence_urls": len(sentence_urls) >= 1,
            "responses_present": len(responses) >= 2,
        }
        passed = sum(checks.values())
        score = round((passed / len(checks)) * 100, 1)
        return {
            "accepted": score >= self.minimum_score,
            "score": score,
            "checks": checks,
            "required_score": self.minimum_score,
            "valid_sentence_count": len(valid_sentences),
            "sentence_source_count": len(sentence_sources),
        }
