from __future__ import annotations

import re

from arastirma.web_arastirici import WebArastirici


class CumleMotoru:
    """Kelime için web araştırmasından gerçek kullanım cümleleri çıkarmaya çalışır."""

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=10)

    async def research(self, word, research, usage):
        # Sadece önceki kullanım snippet'lerine güvenme; cümle araştırmasını
        # ayrıca hedefleyen aramalar yap.
        queries = [
            f'"{word}" "örnek cümle"',
            f'"{word}" cümle içinde kullanım',
            f'"{word}" "şöyle" cümle',
            f'"{word}" günlük hayatta cümle',
            f'"{word}" haber cümle kullanım',
        ]

        candidates = []
        seen = set()

        # Önceki kullanım araştırmasının verilerini de değerlendir.
        for item in usage.get("contexts", []):
            self._extract_from_text(word, item, candidates, seen, "usage_research")

        # Hedefli web aramalarından cümle adaylarını çıkar.
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

        return candidates[:15]

    def _extract_from_text(self, word, text, candidates, seen, source, url=""):
        if not text:
            return

        # HTML/arama motoru artıkları ve fazla boşlukları temizle.
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # Noktalama işaretlerinden gerçek cümle parçalarını ayır.
        parts = re.split(r"(?<=[.!?])\s+|\s+[•·]\s+|\s+[–—-]\s+", text)
        for part in parts:
            sentence = part.strip(" \t\r\n-–—•·\"'“”‘’")
            sentence = re.sub(r"\s+", " ", sentence).strip()

            if not self._is_valid_candidate(word, sentence):
                continue

            key = " ".join(sentence.casefold().split())
            if key in seen:
                continue
            seen.add(key)

            candidates.append({
                "sentence": sentence,
                "source": source,
                "url": url,
            })

    @staticmethod
    def _is_valid_candidate(word, sentence):
        if len(sentence) < 25 or len(sentence) > 300:
            return False
        if word.casefold() not in sentence.casefold():
            return False

        # Arama başlığı/snippet'i gibi duran parçaları ele.
        lower = sentence.casefold()
        junk = (
            "ne demek", "anlamı", "sözlük", "tdk", "arama sonuçları",
            "wikipedia", "translate", "çeviri", "giriş yap", "devamını oku",
        )
        if any(marker in lower for marker in junk):
            return False

        # En az birkaç kelimelik doğal bir yapı bekle.
        words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", sentence, flags=re.UNICODE)
        if len(words) < 5:
            return False

        # URL veya HTML kalıntısı içerenleri alma.
        if "http://" in lower or "https://" in lower or "www." in lower:
            return False

        return True
