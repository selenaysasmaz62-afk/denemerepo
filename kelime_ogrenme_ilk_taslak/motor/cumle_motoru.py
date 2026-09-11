from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici


class CumleMotoru:
    """Kelime için gerçek kullanım cümleleri toplar; Tatoeba'yı yedek kaynak kullanır."""

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=8)

    async def research(self, word, research, usage):
        candidates = []
        seen = set()

        if isinstance(usage, dict):
            for item in usage.get("contexts", []) or []:
                self._extract_from_text(word, item, candidates, seen, "usage_research")

        # Tek hedefli web sorgusu; sonuç yoksa gerçek örnek cümle API'sine geç.
        data = await self.web.search(f'"{word}" örnek cümle kullanım')
        for result in data.get("results", []):
            text = f'{result.get("title", "")}. {result.get("snippet", "")}'.strip()
            self._extract_from_text(word, text, candidates, seen, "web_sentence_research", result.get("url", ""))
            if len(candidates) >= 15:
                break

        if not candidates:
            for sentence in await self._tatoeba_sentences(word):
                self._extract_from_text(word, sentence, candidates, seen, "tatoeba", "https://tatoeba.org/")
                if len(candidates) >= 15:
                    break

        # Son yedek: araştırma kaynakları; yalnızca cümle filtresini geçerse kabul edilir.
        if not candidates and isinstance(research, dict):
            for result in research.get("sources", []) or []:
                text = f'{result.get("title", "")}. {result.get("snippet", "")}'.strip()
                self._extract_from_text(word, text, candidates, seen, "research_source_fallback", result.get("url", ""))
                if len(candidates) >= 15:
                    break

        return candidates[:15]

    async def _tatoeba_sentences(self, word):
        try:
            url = (
                "https://tatoeba.org/en/api_v0/search?from=tur"
                f"&query={quote_plus(word)}&to=tur&orphans=no&sort=relevance&limit=20"
            )
            raw = await asyncio.to_thread(self._fetch_json, url)
            payload = json.loads(raw)
            return [
                item.get("text", "")
                for item in payload.get("results", [])
                if isinstance(item, dict) and item.get("text")
            ]
        except Exception:
            return []

    @staticmethod
    def _fetch_json(url):
        request = Request(
            url,
            headers={
                "User-Agent": "FatosKelimeOgrenmeTest/1.0",
                "Accept": "application/json",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
            },
        )
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")

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
            sentence = self._clean_prefix(sentence)
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
    def _clean_prefix(sentence):
        return re.sub(
            r"^(?:örnek cümle|örnek kullanım|cümle içinde|kullanım örneği)\s*[:\-–—]?\s*",
            "", sentence, flags=re.IGNORECASE,
        ).strip()

    @staticmethod
    def _is_valid_candidate(word, sentence):
        if len(sentence) < 12 or len(sentence) > 300:
            return False
        if word.casefold() not in sentence.casefold():
            return False
        lower = sentence.casefold()
        junk = (
            "arama sonuçları", "wikipedia", "translate", "çeviri", "giriş yap",
            "devamını oku", "cookie", "gizlilik politikası", "sözlük", "ne demek",
        )
        if any(marker in lower for marker in junk):
            return False
        words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", sentence, flags=re.UNICODE)
        if len(words) < 3:
            return False
        if "http://" in lower or "https://" in lower or "www." in lower:
            return False
        if sentence.count("|") >= 2 or sentence.count("/") >= 3:
            return False
        return True
