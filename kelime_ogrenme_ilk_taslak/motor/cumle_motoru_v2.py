from __future__ import annotations

import asyncio
import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici


class CumleMotoruV2:
    """Gerçek Türkçe kullanım cümlelerini birden fazla kanaldan toplar."""

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=8)

    async def research(self, word, research, usage):
        candidates, seen = [], set()

        for sentence in await self._tatoeba_sentences(word):
            self._add_sentence(word, sentence, candidates, seen, "tatoeba", "https://tatoeba.org/")
            if len(candidates) >= 15:
                return candidates[:15]

        if len(candidates) < 6:
            for query in (
                f'"{word}" "örnek cümle"',
                f'"{word}" "örnek kullanım"',
                f'"{word}" "cümle içinde"',
                f'"{word}" "kullanım örneği"',
                f'"{word}" günlük kullanım',
            ):
                data = await self.web.search(query)
                for result in data.get("results", []):
                    if not isinstance(result, dict):
                        continue
                    text = result.get("snippet", "") or result.get("title", "")
                    self._extract_from_text(word, text, candidates, seen, "web_sentence_research", result.get("url", ""))
                    if len(candidates) >= 15:
                        return candidates[:15]

        if len(candidates) < 3 and isinstance(research, dict):
            for result in research.get("sources", []) or []:
                if not isinstance(result, dict):
                    continue
                self._extract_research_examples(
                    word, result.get("snippet", ""), candidates, seen,
                    "research_source_example", result.get("url", ""),
                )
                if len(candidates) >= 15:
                    return candidates[:15]

        if len(candidates) < 3:
            contexts = usage.get("contexts", []) if isinstance(usage, dict) else []
            for context in contexts:
                self._extract_from_text(word, context, candidates, seen, "usage_research", "")
                if len(candidates) >= 15:
                    break

        return candidates[:15]

    async def _tatoeba_sentences(self, word):
        urls = (
            "https://api.tatoeba.org/v1/sentences?"
            f"lang=tur&q={quote_plus(word)}&limit=50",
            "https://api.tatoeba.org/v1/sentences?"
            f"lang=tur&q={quote_plus(word)}&sort=relevance&limit=50",
            "https://api.tatoeba.org/v1/sentences?"
            f"lang=tur&q=%3D{quote_plus(word)}&limit=50",
        )
        for url in urls:
            try:
                payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
                items = payload.get("data", []) if isinstance(payload, dict) else []
                values = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text") or item.get("sentence") or ""
                    if text:
                        values.append(text)
                if values:
                    return values
            except Exception:
                continue
        return []

    @staticmethod
    def _fetch_json(url):
        request = Request(url, headers={
            "User-Agent": "FatosKelimeOgrenmeTest/1.1",
            "Accept": "application/json",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
        })
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")

    def _extract_research_examples(self, word, text, candidates, seen, source, url=""):
        if not text:
            return
        text = html.unescape(str(text))
        matches = re.findall(
            r"(?:örnek|example|örnek cümle|örnek kullanım)\s*[:\-–—]\s*(.+)",
            text,
            flags=re.IGNORECASE,
        )
        for match in matches:
            self._extract_from_text(word, match, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

    def _extract_from_text(self, word, text, candidates, seen, source, url=""):
        if not text:
            return
        text = html.unescape(str(text))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        example_matches = re.findall(
            r"(?:örnek|example|örnek cümle|örnek kullanım|kullanım örneği)\s*[:\-–—]\s*(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if example_matches:
            for example in example_matches:
                self._extract_from_text(word, example, candidates, seen, source, url)
                if len(candidates) >= 15:
                    return
            return

        parts = re.split(r"(?<=[.!?])\s+|\s+[•·]\s+|\s+[–—]\s+", text)
        for part in parts:
            self._add_sentence(word, part, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

    def _add_sentence(self, word, sentence, candidates, seen, source, url=""):
        sentence = html.unescape(str(sentence or ""))
        sentence = re.sub(r"<[^>]+>", " ", sentence)
        sentence = re.sub(r"\s+", " ", sentence).strip()
        sentence = sentence.strip(" \t\r\n-–—•·\"'“”‘’")
        sentence = re.sub(
            r"^(?:örnek cümle|örnek kullanım|cümle içinde|kullanım örneği|örnek)\s*[:\-–—]?\s*",
            "", sentence, flags=re.IGNORECASE,
        ).strip()
        if not self._is_valid_candidate(word, sentence):
            return
        if sentence[-1] not in ".!?":
            sentence += "."
        key = " ".join(sentence.casefold().split())
        if key not in seen:
            seen.add(key)
            candidates.append({"sentence": sentence, "source": source, "url": url})

    @staticmethod
    def _is_valid_candidate(word, sentence):
        if len(sentence) < 12 or len(sentence) > 220:
            return False
        lower = sentence.casefold()
        if word.casefold() not in lower:
            return False
        if any(marker in lower for marker in (
            "arama sonuçları", "wikipedia", "translate", "çeviri", "giriş yap",
            "devamını oku", "cookie", "gizlilik politikası", "sözlük", "ne demek",
            "numaralı adam", "film", "albüm", "şarkı", "oyun", "dizi",
            "http://", "https://", "www.",
        )):
            return False
        if re.match(r"^(?:isim|fiil|sıfat|zarf|edat|ünlem|zamir)\s*[:\-]", lower):
            return False
        words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", sentence, flags=re.UNICODE)
        if len(words) < 4:
            return False
        if sentence.count("|") >= 2 or sentence.count("/") >= 3:
            return False
        return not (sentence.count(",") >= 5 and len(words) < 14)
