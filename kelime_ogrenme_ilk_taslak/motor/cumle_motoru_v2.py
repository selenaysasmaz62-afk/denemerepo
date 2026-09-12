from __future__ import annotations

import asyncio
import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici, _BingSearchParser


class CumleMotoruV2:
    """Gerçek Türkçe kullanım cümlelerini birden fazla kaynaktan toplar."""

    def __init__(self):
        self.web = WebArastirici(timeout=5, max_results=8)

    async def research(self, word, research, usage):
        candidates, seen = [], set()

        if isinstance(usage, dict):
            for sentence in usage.get("contexts", []) or []:
                self._add_sentence(word, sentence, candidates, seen, "usage_research", "")
                if len(candidates) >= 15:
                    return candidates[:15]

        # Öncelik: Tatoeba'dan doğrudan gerçek Türkçe cümleler.
        for item in await self._tatoeba_sentences(word):
            if isinstance(item, dict):
                text = item.get("sentence", "")
                url = item.get("url", "")
            elif isinstance(item, (tuple, list)):
                text = item[0] if item else ""
                url = item[1] if len(item) > 1 else ""
            else:
                text = str(item)
                url = ""

            self._add_sentence(
                word,
                text,
                candidates,
                seen,
                "tatoeba",
                url,
            )
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
                data = await self._bing_search(query)
                if not data:
                    continue
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

    async def _bing_search(self, query):
        """Tek Bing isteğini ayrı süreçte çalıştırır; ağ kilitlenirse event loop kapanmaz."""
        url = "https://www.bing.com/search?q=" + quote_plus(query) + "&setlang=tr"
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "curl", "-L", "--silent", "--show-error", "--max-time", "5",
                "-A", "FatosKelimeOgrenmeTest/1.0", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=6)
            if process.returncode != 0 or not stdout:
                return None
            parser = _BingSearchParser()
            parser.feed(stdout.decode("utf-8", errors="replace"))
            parser.close()
            results = parser.results[:8]
            return {
                "query": query,
                "results": results,
                "error": None,
                "provider": "https://www.bing.com/search",
            }
        except Exception:
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
            return None

    async def _fetch_url_text(self, url, accept="application/json"):
        """HTTP isteğini ayrı curl sürecinde yapar; urlopen thread kilitlenmesini önler."""
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "curl", "-L", "--silent", "--show-error", "--max-time", "5",
                "-A", "FatosKelimeOgrenmeTest/1.4",
                "-H", f"Accept: {accept}",
                "-H", "Accept-Language: tr-TR,tr;q=0.9,en;q=0.7",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=6)
            if process.returncode != 0 or not stdout:
                return ""
            return stdout.decode("utf-8", errors="replace")
        except Exception:
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
            return ""

    async def _tatoeba_sentences(self, word):
        url = "https://api.tatoeba.org/v1/sentences?" f"lang=tur&q={quote_plus(word)}&sort=relevance&limit=50"
        try:
            raw = await self._fetch_url_text(url)
            payload = json.loads(raw)
            items = payload.get("data", []) if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                return []
            values = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                text = self._clean_text(item.get("text") or item.get("sentence") or "")
                if text and self._contains_target_word(word, text):
                    values.append((text, "https://api.tatoeba.org/"))
            return values
        except Exception:
            return []

    async def _dictionary_examples(self, word):
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/tr/{quote_plus(word)}"
            raw = await self._fetch_url_text(url)
            payload = json.loads(raw)
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
            raw = await self._fetch_url_text(url)
            payload = json.loads(raw)
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
        with urlopen(request, timeout=5) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _fetch_html_text(url):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) FatosKelimeOgrenmeTest/1.4", "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7"})
            with urlopen(request, timeout=5) as response:
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
            # Bing snippetlerini doğrudan cümle kabul etme.
            # Yalnızca gerçekten cümle görünümünde olan parçaları kabul et.
            if not sentence or not re.match(r"^[A-ZÇĞİÖŞÜ]", sentence):
                return
            if not re.search(r"[.!?]$", sentence):
                return
            web_lower = sentence.casefold().replace("\u0307", "")
            if "..." in sentence or "…" in sentence:
                return
            if re.match(r"^(?:Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)\s+\d{4}", sentence, re.IGNORECASE):
                return
            if re.match(r"^\d{1,2}\s+(?:Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)\s+\d{4}", sentence, re.IGNORECASE):
                return
            if any(marker in web_lower for marker in (
                "örnek cümle", "örnek cümle:", "örnek kullanım",
                "anlamı", "anlamıdır", "anlamı:", "sıfat olarak",
                "isim olarak", "fiil olarak", "kelimesinin",
                "kelimesi", "nasıl kullanılır", "cümle:",
                "cümleler", "sözlük", "türkçenin en", "türkçede",
            )):
                return
            if re.search(r"\b(?:ve|ile|için|olarak|ayrıca|gibi|diye)\s*[.!?]$", web_lower):
                return
            words = sentence.split()
            if len(words) < 4:
                return
            self._add_sentence(word, sentence, candidates, seen, source, url)
            return
            parts = re.split(r"(?<=[.!?])\s+", text)
            for part in parts:
                part = part.strip()
                if self._contains_target_word(word, part):
                    self._add_sentence(word, part, candidates, seen, source, url)
                    if len(candidates) >= 15:
                        return

            # Bing bazı gerçek cümleleri noktalamasız snippet olarak döndürür.
            # Bu durumda hedef kelimenin çevresindeki kısa cümle parçasını dene.
            if len(candidates) < 15 and self._contains_target_word(word, text):
                words = text.split()
                target_index = next(
                    (
                        i for i, value in enumerate(words)
                        if self._contains_target_word(word, value)
                    ),
                    None,
                )
                if target_index is not None:
                    start = max(0, target_index - 7)
                    end = min(len(words), target_index + 8)
                    fragment = " ".join(words[start:end]).strip()
                    fragment = re.sub(r"^[^A-Za-zÇĞİÖŞÜçğıöşü]+", "", fragment)
                    fragment = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü0-9.,!?;:()'’\- ]+$", "", fragment)
                    self._add_sentence(word, fragment, candidates, seen, source, url)

            return

        parts = re.split(r"(?<=[.!?])\s+|\s*[•·]\s*|\s*\*\s*", text)
        for part in parts:
            self._add_sentence(word, part, candidates, seen, source, url)
            if len(candidates) >= 15:
                return

    def _add_sentence(self, word, sentence, candidates, seen, source, url=""):
        sentence = self._clean_text(sentence)
        sentence = sentence.strip(" \t\r\n-–—•·*\"'“”‘’")

        # Web arama sonuçlarında açıklama/parça cümleleri gerçek kullanım
        # cümlesi değildir. Bunları daha validation'a gelmeden ele.
        if source == "web_sentence_research":
            # Bing snippetlerini doğrudan cümle kabul etme.
            # Yalnızca gerçekten cümle görünümünde olan parçaları kabul et.
            if not sentence or not re.match(r"^[A-ZÇĞİÖŞÜ]", sentence):
                return
            if not re.search(r"[.!?]$", sentence):
                return
            web_lower = sentence.casefold().replace("\u0307", "")
            if "..." in sentence or "…" in sentence:
                return
            if re.match(r"^(?:Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)\s+\d{4}", sentence, re.IGNORECASE):
                return
            if re.match(r"^\d{1,2}\s+(?:Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)\s+\d{4}", sentence, re.IGNORECASE):
                return
            if any(marker in web_lower for marker in (
                "örnek cümle", "örnek cümle:", "örnek kullanım",
                "anlamı", "anlamıdır", "anlamı:", "sıfat olarak",
                "isim olarak", "fiil olarak", "kelimesinin",
                "kelimesi", "nasıl kullanılır", "cümle:",
                "cümleler", "sözlük", "türkçenin en", "türkçede",
            )):
                return
            if re.search(r"\b(?:ve|ile|için|olarak|ayrıca|gibi|diye)\s*[.!?]$", web_lower):
                return
            words = sentence.split()
            if len(words) < 4:
                return
            self._add_sentence(word, sentence, candidates, seen, source, url)
            return
