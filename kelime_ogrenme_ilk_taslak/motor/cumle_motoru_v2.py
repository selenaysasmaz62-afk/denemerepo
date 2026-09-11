from __future__ import annotations

import asyncio
import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici


class CumleMotoruV2:
    """Gerçek Türkçe kullanım cümlelerini birden fazla güvenilir kanaldan toplar."""

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=8)

    async def research(self, word, research, usage):
        candidates, seen = [], set()

        # 1) Tatoeba API v1 + eski API yedeği.
        for sentence, url in await self._tatoeba_sentences(word):
            self._add_sentence(word, sentence, candidates, seen, "tatoeba", url)
            if len(candidates) >= 15:
                return candidates[:15]

        # 2) Türkçe sözlük API'lerindeki gerçek example alanları.
        for sentence, url in await self._dictionary_examples(word):
            self._add_sentence(word, sentence, candidates, seen, "dictionary_example", url)
            if len(candidates) >= 15:
                return candidates[:15]

        # 3) Türkçe Vikisözlük sayfasındaki örnek cümleler.
        for sentence, url in await self._wiktionary_examples(word):
            self._add_sentence(word, sentence, candidates, seen, "vikisozluk_example", url)
            if len(candidates) >= 15:
                return candidates[:15]

        # 4) Web araması. Arama motoru sonuç vermese bile üstteki kaynaklar
        # bağımsız çalışır; başlıklar burada cümle olarak kullanılmaz.
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
                    if not snippet:
                        continue
                    self._extract_from_text(
                        word, snippet, candidates, seen,
                        "web_sentence_research", result.get("url", ""),
                    )
                    if len(candidates) >= 15:
                        return candidates[:15]

        # 5) Araştırma kaynaklarında açıkça belirtilmiş örnek cümleler.
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

        # 6) Kullanım bağlamı son yedektir; başlık değil, sadece metin kullanılır.
        if len(candidates) < 3:
            contexts = usage.get("contexts", []) if isinstance(usage, dict) else []
            for context in contexts:
                self._extract_from_text(word, context, candidates, seen, "usage_research", "")
                if len(candidates) >= 15:
                    break

        return candidates[:15]

    async def _tatoeba_sentences(self, word):
        urls = (
            (
                "https://api.tatoeba.org/v1/sentences?"
                f"lang=tur&q={quote_plus(word)}&limit=50",
                "https://api.tatoeba.org/",
            ),
            (
                "https://api.tatoeba.org/v1/sentences?"
                f"lang=tur&q={quote_plus(word)}&sort=relevance&limit=50",
                "https://api.tatoeba.org/",
            ),
            (
                "https://tatoeba.org/eng/api_v0/search?"
                f"from=tur&query={quote_plus(word)}&limit=50",
                "https://tatoeba.org/",
            ),
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
                    text = item.get("text") or item.get("sentence") or ""
                    if text:
                        values.append((text, source_url))
                if values:
                    return values
            except Exception:
                continue
        return []

    async def _dictionary_examples(self, word):
        """Dictionary API'deki example alanlarını doğrudan toplar."""
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/tr/{quote_plus(word)}"
            payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
            values = []
            for entry in payload if isinstance(payload, list) else []:
                for meaning in entry.get("meanings", []) or []:
                    for definition in meaning.get("definitions", []) or []:
                        example = self._clean_text(definition.get("example", ""))
                        if example:
                            values.append((example, "https://api.dictionaryapi.dev/"))
            return values
        except Exception:
            return []

    async def _wiktionary_examples(self, word):
        """Türkçe Vikisözlük maddesinden açık örnek cümleleri çıkarır."""
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
                    if not line:
                        continue
                    # Vikisözlükte örnek bölümlerini hedefle; tanım satırlarını
                    # doğrudan cümle diye kabul etme.
                    if re.search(r"(?:örnek|örnekler|kullanım)", line, re.I):
                        self._extract_from_text(
                            word, line, values_as_candidates := [], set(),
                            "vikisozluk_example", "https://tr.wiktionary.org/"
                        )
                        for item in values_as_candidates:
                            values.append((item["sentence"], "https://tr.wiktionary.org/"))
            return values
        except Exception:
            return []

    @staticmethod
    def _fetch_json(url):
        request = Request(
            url,
            headers={
                "User-Agent": "FatosKelimeOgrenmeTest/1.2",
                "Accept": "application/json",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
            },
        )
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _clean_text(value):
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _extract_research_examples(self, word, text, candidates, seen, source, url=""):
        if not text:
            return
        text = self._clean_text(text)
        matches = re.findall(
            r"(?:örnek|example|örnek cümle|örnek kullanım|kullanım örneği)\s*[:\-–—]\s*(.+)",
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
        text = self._clean_text(text)

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
        sentence = self._clean_text(sentence)
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
