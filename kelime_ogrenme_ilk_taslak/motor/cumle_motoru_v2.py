from __future__ import annotations

import asyncio
import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici


class CumleMotoruV2:
    """Gerçek Türkçe kullanım cümlelerini birden fazla kaynaktan toplar."""

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=8)

    async def research(self, word, research, usage):
        candidates, seen = [], set()

        for sentence, url in await self._tatoeba_sentences(word):
            self._add_sentence(word, sentence, candidates, seen, "tatoeba", url)
            if len(candidates) >= 15:
                return candidates[:15]

        for sentence, url in await self._dictionary_examples(word):
            self._add_sentence(word, sentence, candidates, seen, "dictionary_example", url)
            if len(candidates) >= 15:
                return candidates[:15]

        for sentence, url in await self._wiktionary_examples(word):
            self._add_sentence(word, sentence, candidates, seen, "vikisozluk_example", url)
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
                    snippet = result.get("snippet", "") or ""
                    url = result.get("url", "") or ""
                    if not snippet:
                        continue
                    self._extract_from_text(word, snippet, candidates, seen, "web_sentence_research", url)
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

        return candidates[:15]

    async def _tatoeba_sentences(self, word):
        urls = (
            ("https://api.tatoeba.org/v1/sentences?" f"lang=tur&q={quote_plus(word)}&limit=50", "https://api.tatoeba.org/"),
            ("https://api.tatoeba.org/v1/sentences?" f"lang=tur&q={quote_plus(word)}&sort=relevance&limit=50", "https://api.tatoeba.org/"),
            ("https://tatoeba.org/eng/api_v0/search?" f"from=tur&query={quote_plus(word)}&limit=50", "https://tatoeba.org/"),
        )
        for url, source_url in urls:
            try:
                payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
                items = payload.get("data", []) if isinstance(payload, dict) else payload
                if not isinstance(items, list):
                    continue
                values = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    text = self._clean_text(item.get("text") or item.get("sentence") or "")
                    if text and self._contains_target_word(word, text):
                        values.append((text, source_url))
                if values:
                    return values
            except Exception:
                continue
        return []

    async def _dictionary_examples(self, word):
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/tr/{quote_plus(word)}"
            payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
            values = []
            for entry in payload if isinstance(payload, list) else []:
                for meaning in entry.get("meanings", []) or []:
                    for definition in meaning.get("definitions", []) or []:
                        example = self._clean_text(definition.get("example", ""))
                        if example and self._contains_target_word(word, example):
                            values.append((example, "https://api.dictionaryapi.dev/"))
            return values
        except Exception:
            return []

    async def _wiktionary_examples(self, word):
        try:
            url = (
                "https://tr.wiktionary.org/w/api.php?action=query&prop=extracts"
                f"&explaintext=1&titles={quote_plus(word)}&format=json&utf8=1"
            )
            payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
            pages = payload.get("query", {}).get("pages", {})
            values = []
            for page in pages.values():
                extract = page.get("extract", "") if isinstance(page, dict) else ""
                if not extract:
                    continue
                for line in re.split(r"\n+", extract):
                    line = self._clean_text(line)
                    if not line or not re.search(r"(?:örnek|örnekler|kullanım)", line, re.I):
                        continue
                    extracted = []
                    self._extract_from_text(word, line, extracted, set(), "vikisozluk_example", "https://tr.wiktionary.org/")
                    for item in extracted:
                        values.append((item["sentence"], "https://tr.wiktionary.org/"))
            return values
        except Exception:
            return []

    @staticmethod
    def _fetch_json(url):
        request = Request(url, headers={"User-Agent": "FatosKelimeOgrenmeTest/1.4", "Accept": "application/json", "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7"})
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _fetch_html_text(url):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) FatosKelimeOgrenmeTest/1.4", "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7"})
            with urlopen(request, timeout=10) as response:
                raw = response.read().decode("utf-8", errors="replace")
            raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<noscript\b[^>]*>.*?</noscript>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<[^>]+>", " ", raw)
            return re.sub(r"\s+", " ", html.unescape(raw)).strip()
        except Exception:
            return ""

    @staticmethod
    def _clean_text(value):
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _contains_target_word(word, text):
        escaped = re.escape(word.strip())
        if not escaped:
            return False
        return re.search(rf"(?<![\wçğıöşüÇĞİÖŞÜ]){escaped}(?![\wçğıöşüÇĞİÖŞÜ])", text, flags=re.IGNORECASE) is not None

    def _extract_research_examples(self, word, text, candidates, seen, source, url=""):
        if not text:
            return
        text = self._clean_text(text)
        matches = re.findall(r"(?:örnek cümle|örnek kullanım|kullanım örneği|example|örnek)\s*[:\-–—]\s*(.+)", text, flags=re.IGNORECASE)
        for match in matches:
            self._extract_from_text(word, match, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

    def _extract_from_text(self, word, text, candidates, seen, source, url=""):
        if not text:
            return
        text = self._clean_text(text)
        if not text:
            return

        quoted = re.findall(r"[\"“”‘’']([^\"“”‘’']{12,220})[\"“”‘’']", text, flags=re.UNICODE)
        for item in quoted:
            self._add_sentence(word, item, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

        numbered = re.findall(r"(?:^|\s)(?:\d+\s*[.)])\s*(.+?)(?=\s+\d+\s*[.)]\s*|$)", text, flags=re.IGNORECASE)
        for item in numbered:
            self._add_sentence(word, item, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

        bullets = re.findall(r"(?:^|\s)(?:[*•·]|[-–—])\s*(.+?)(?=\s+(?:[*•·]|[-–—])\s*|$)", text, flags=re.UNICODE)
        for item in bullets:
            self._add_sentence(word, item, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

        example_matches = re.findall(r"(?:örnek cümle|örnek kullanım|kullanım örneği|example|örnek)\s*[:\-–—]\s*(.+)", text, flags=re.IGNORECASE)
        for example in example_matches:
            if example.strip() == text.strip():
                continue
            self._extract_from_text(word, example, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

        if source == "web_sentence_research":
            return

        parts = re.split(r"(?<=[.!?])\s+|\s*[•·]\s*|\s*\*\s*", text)
        for part in parts:
            self._add_sentence(word, part, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

    def _add_sentence(self, word, sentence, candidates, seen, source, url=""):
        sentence = self._clean_text(sentence)
        sentence = sentence.strip(" \t\r\n-–—•·*\"'“”‘’")
        sentence = re.sub(r"^(?:\d+\s*[.)]|[-–—•·*])\s*", "", sentence).strip()
        sentence = re.sub(r"^(?:örnek cümle|örnek kullanım|cümle içinde|kullanım örneği|örnek)\s*[:\-–—]?\s*", "", sentence, flags=re.IGNORECASE).strip()
        if not self._is_valid_candidate(word, sentence):
            return
        if sentence[-1] not in ".!?":
            sentence += "."
        key = " ".join(sentence.casefold().split())
        if key not in seen:
            seen.add(key)
            candidates.append({"sentence": sentence, "source": source, "url": url})

    @classmethod
    def _is_valid_candidate(cls, word, sentence):
        if len(sentence) < 12 or len(sentence) > 220:
            return False
        lower = sentence.casefold().replace("\u0307", "")
        if not cls._contains_target_word(word, sentence):
            return False
        if any(marker in lower for marker in (
            "arama sonuçları", "wikipedia", "translate", "çeviri", "giriş yap", "devamını oku", "cookie",
            "gizlilik politikası", "sözlük", "ne demek", "numaralı adam", "film", "albüm", "şarkı", "oyun", "dizi",
            "kelimesi ile ilgili cümleler", "kelimesi ile ilgili", "kelimesinin ile ilgili", "bir cümlede", "örnek cümleler",
            "ifadesini nasıl kullanacağınızı", "aşağıdaki anlamlara gelebilir", "gerçek ve mecaz anlam", "mecaz anlamda",
            "cevap:", "cevabımda", "aşağıda", "örnekler vereyim", "çok anlamlılık denir", "soru çözme",
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
