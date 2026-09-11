from __future__ import annotations

import re

from arastirma.web_arastirici import WebArastirici


class CumleMotoru:
    """Kelime için web araştırmasından gerçekçi kullanım cümleleri çıkarır."""

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=10)

    async def research(self, word, research, usage):
        queries = [
            f'"{word}" örnek cümle',
            f'"{word}" cümle içinde kullanım',
            f'"{word}" günlük kullanım örneği',
            f'"{word}" haber cümlesi',
            f'"{word}" nasıl kullanılır cümle',
        ]

        candidates = []
        seen = set()

        if isinstance(usage, dict):
            for item in usage.get("contexts", []) or []:
                self._extract_from_text(word, item, candidates, seen, "usage_research")

        for query in queries:
            data = await self.web.search(query)
            for result in data.get("results", []):
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                source_url = result.get("url", "")
                text = f"{title}. {snippet}".strip()
                self._extract_from_text(
                    word, text, candidates, seen, "web_sentence_research", source_url
                )
                if len(candidates) >= 15:
                    break
            if len(candidates) >= 15:
                break

        # Hedefli cümle aramaları sonuç vermezse ilk araştırmanın kaynak
        # snippet'lerini son aday havuzu olarak değerlendir.
        if not candidates and isinstance(research, dict):
            for result in research.get("sources", []) or []:
                text = f'{result.get("title", "")}. {result.get("snippet", "")}'.strip()
                self._extract_from_text(
                    word, text, candidates, seen, "research_source_fallback", result.get("url", "")
                )
                if len(candidates) >= 15:
                    break

        return candidates[:15]

    def _extract_from_text(self, word, text, candidates, seen, source, url=""):
        if not text:
            return

        text = re.sub(r"<[^>]+>", " ", str(text))
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return

        parts = re.split(r"(?<=[.!?])\s+|\s+[•·]\s+|\s+[–—]\s+", text)
        possible = list(parts)
        if len(parts) == 1:
            possible.append(text)

        for part in possible:
            sentence = part.strip(" \t\r\n-–—•·\"'“”‘’")
            sentence = re.sub(r"\s+", " ", sentence).strip()
            sentence = self._clean_prefix(word, sentence)

            if not self._is_valid_candidate(word, sentence):
                continue

            if sentence[-1] not in ".!?":
                sentence += "."

            key = " ".join(sentence.casefold().split())
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"sentence": sentence, "source": source, "url": url})

    @staticmethod
    def _clean_prefix(word, sentence):
        sentence = re.sub(
            rf"^(?:örnek cümle|örnek kullanım|cümle içinde|kullanım örneği)\s*[:\-–—]?\s*",
            "", sentence, flags=re.IGNORECASE,
        )
        return sentence.strip()

    @staticmethod
    def _is_valid_candidate(word, sentence):
        if len(sentence) < 18 or len(sentence) > 300:
            return False
        if word.casefold() not in sentence.casefold():
            return False

        lower = sentence.casefold()
        junk = (
            "arama sonuçları", "wikipedia", "translate", "çeviri", "giriş yap",
            "devamını oku", "cookie", "gizlilik politikası",
        )
        if any(marker in lower for marker in junk):
            return False

        words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", sentence, flags=re.UNICODE)
        if len(words) < 4:
            return False
        if "http://" in lower or "https://" in lower or "www." in lower:
            return False
        if sentence.count("|") >= 2 or sentence.count("/") >= 3:
            return False

        return True
