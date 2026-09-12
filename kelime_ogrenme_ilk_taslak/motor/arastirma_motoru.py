from __future__ import annotations

import asyncio
import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici, _BingSearchParser


class KelimeArastirmaMotoru:
    """Kelime anlamlarını ve kullanımlarını birden fazla kaynaktan toplar."""

    _JUNK_TITLE = (
        "numaralı adam", "gizli yüz", "iskeleti", "tanıma sistemi",
        "film", "albüm", "şarkı", "oyun", "dizi", "bölüm",
    )

    _USAGE_JUNK = (
        "bir cümlede ", "ifadesini nasıl kullanacağınızı",
        "kelimesini içeren çok sayıda", "kelimesi ile ilgili",
        "kelimesinin ile ilgili", "kelimesinin hem gerçek anlamı",
        "kelimesinin hem mecaz anlamı", "örnek cümleler vereyim",
        "örnek cümleleri", "gerçek ve mecaz anlam",
        "aşağıda her iki anlamı", "kullanım bağlamına göre",
        "gövde anlamlar", "incehesap.com", "muharrem ince",
        "resmi web sitesidir", "erişim tarihi", "kendinize meydan okuyun",
        "daha hafif bir modelden", "bu cümlede ",
        "cümlede “", "cümlede \"",
    )

    def __init__(self):
        self.web = WebArastirici(timeout=5, max_results=8)

    async def _bing_search(self, query):
        url = "https://www.bing.com/search?q=" + quote_plus(query) + "&setlang=tr"
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "curl", "-L", "--silent", "--max-time", "5",
                "-A", "FatosKelimeOgrenmeTest/1.0", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=6)
            if process.returncode != 0 or not stdout:
                return None
            results = _BingSearchParser().parse(stdout.decode("utf-8", errors="replace"), url)
            return {"query": query, "results": results[:8], "error": None, "provider": "https://www.bing.com/search"}
        except Exception:
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
            return None

    async def research(self, word):
        results = []
        seen = set()
        queries = (
            f'"{word}" anlamı',
            f'"{word}" ne demek',
            f'"{word}" sözlük',
            f'"{word}" Türkçe anlamı',
        )
        responses = await asyncio.gather(*(self._bing_search(query) for query in queries), return_exceptions=True)
        for data in responses:
            if isinstance(data, dict):
                self._append_results(results, seen, data.get("results", []))
                if len(results) >= 16:
                    break

        # Arama motoru belirli sorguları boş döndürürse daha genel tek bir yedek sorgu dene.
        if not results:
            fallback = await self._bing_search(f'"{word}" Türkçe')
            if isinstance(fallback, dict):
                self._append_results(results, seen, fallback.get("results", []))

        ranked = sorted(results, key=lambda item: self._result_score(word, item), reverse=True)
        senses = self._build_senses(word, ranked)
        return {"word": word, "senses": senses, "meanings": [s["definition"] for s in senses][:12], "sources": ranked[:12]}

    async def _usage_web_search(self, query):
        return await self._bing_search(query)

    async def research_usage(self, word, research):
        contexts = []
        patterns = []
        seen = set()
        query = f'"{word}" "örnek cümle"'

        data = await self._usage_web_search(query)

        if isinstance(data, dict):
            self._append_contexts(contexts, seen, data.get("results", []), word)

        if not contexts:
            self._append_contexts(contexts, seen, research.get("sources", []) if isinstance(research, dict) else [], word)

        lower = word.casefold().replace("\u0307", "")
        for context in contexts:
            if lower in context.casefold().replace("\u0307", ""):
                patterns.append(f'"{word}" kullanım bağlamı: {context}')
        return {"word": word, "contexts": contexts[:15], "patterns": patterns[:10]}

    @classmethod
    def _result_score(cls, word, result):
        title = cls._clean_text(result.get("title", "")).casefold()
        snippet = cls._clean_text(result.get("snippet", "")).casefold()
        text = f"{title} {snippet}"
        score = 0
        if word.casefold() in title: score += 3
        for marker in ("tdk", "sözlük", "anlamı", "ne demek", "tanım", "dictionary"):
            if marker in text: score += 4
        if "wikipedia" in title: score += 1
        if any(marker in title for marker in cls._JUNK_TITLE): score -= 10
        if len(snippet) >= 40: score += 2
        if result.get("url"): score += 1
        return score

    @classmethod
    def _build_senses(cls, word, results):
        senses = []
        seen = set()
        for result in results:
            title = cls._clean_text(result.get("title", ""))
            snippet = cls._clean_text(result.get("snippet", ""))
            if not snippet or any(marker in title.casefold() for marker in cls._JUNK_TITLE): continue
            definition = cls._clean_text(re.sub(r"^(?:anlamı|tanımı|sözlük anlamı)\s*[:\-]\s*", "", snippet, flags=re.I))
            key = definition.casefold()
            if len(definition) < 20 or key in seen: continue
            seen.add(key)
            senses.append({"definition": definition, "part_of_speech": cls._guess_part_of_speech(definition), "source_title": title, "source_url": result.get("url", "") or ""})
            if len(senses) >= 8: break
        return senses

    @staticmethod
    def _guess_part_of_speech(text):
        lower = text.casefold()
        if any(x in lower for x in ("fiil", "eylem", "-mek", "-mak")): return "fiil"
        if "sıfat" in lower: return "sıfat"
        if "zarf" in lower: return "zarf"
        if "isim" in lower or "ad " in lower: return "isim"
        return "belirsiz"

    @staticmethod
    def _clean_text(value):
        return " ".join(html.unescape(str(value or "")).split()).strip()

    @classmethod
    def _append_results(cls, results, seen, items):
        for result in items:
            if not isinstance(result, dict): continue
            clean = {"title": cls._clean_text(result.get("title", "")), "snippet": cls._clean_text(result.get("snippet", "")), "url": result.get("url", "") or ""}
            key = clean["url"] or f'{clean["title"]}|{clean["snippet"]}'
            if key and key not in seen:
                seen.add(key); results.append(clean)

    @classmethod
    def _is_usage_context_valid(cls, word, text):
        normalized = cls._clean_text(text)
        lower = normalized.casefold().replace("\u0307", "")
        word_lower = word.casefold().replace("\u0307", "")
        if not normalized or len(normalized) < 12 or word_lower not in lower: return False
        if any(marker in lower for marker in cls._USAGE_JUNK): return False
        if "http://" in lower or "https://" in lower or "www." in lower: return False
        if normalized.count("…") or "..." in normalized or normalized.endswith(":"): return False
        return True

    @classmethod
    def _extract_usage_sentences(cls, word, text):
        text = cls._clean_text(text)
        if not text: return []
        parts = re.split(r"(?<=[.!?])\s+|\s*[•*]\s*|\s*\d+[.)]\s*", text)
        return [c for p in parts if (c := cls._clean_text(p).strip("-–—•* ")) and cls._is_usage_context_valid(word, c)]

    @classmethod
    def _append_contexts(cls, contexts, seen, items, word):
        for result in items:
            if isinstance(result, str):
                text = cls._clean_text(result)
            elif isinstance(result, dict):
                text = cls._clean_text(result.get("snippet", "")) or cls._clean_text(result.get("title", ""))
            else: continue
            candidates = cls._extract_usage_sentences(word, text)
            if not candidates and cls._is_usage_context_valid(word, text): candidates = [text]
            for candidate in candidates:
                key = " ".join(candidate.casefold().split())
                if candidate and key not in seen:
                    seen.add(key); contexts.append(candidate)
                    if len(contexts) >= 15: return

    async def _dictionary_results(self, word):
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/tr/{quote_plus(word)}"
            payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
            results = []
            for entry in payload if isinstance(payload, list) else []:
                for meaning in entry.get("meanings", []):
                    pos = meaning.get("partOfSpeech", "")
                    for definition in meaning.get("definitions", []):
                        text = self._clean_text(definition.get("definition", "")); example = self._clean_text(definition.get("example", ""))
                        if not text: continue
                        snippet = f"{pos}: {text}" if pos else text
                        if example: snippet += f" Örnek: {example}"
                        results.append({"title": f"Dictionary API — {word}", "snippet": snippet, "url": "https://api.dictionaryapi.dev/"})
            return results[:8]
        except Exception: return []

    async def _wikipedia_results(self, word):
        try:
            url = "https://tr.wikipedia.org/w/api.php?action=query&list=search" f"&srsearch={quote_plus(word)}&format=json&utf8=1&srlimit=5"
            payload = json.loads(await asyncio.to_thread(self._fetch_json, url)); results = []
            for item in payload.get("query", {}).get("search", []):
                title = self._clean_text(item.get("title", "")); snippet = self._clean_text(item.get("snippet", "") or "")
                if title or snippet:
                    results.append({"title": f"Vikipedi — {title or word}", "snippet": snippet, "url": f"https://tr.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}" if title else "https://tr.wikipedia.org/"})
            return results
        except Exception: return []

    @staticmethod
    def _fetch_json(url):
        request = Request(url, headers={"User-Agent": "FatosKelimeOgrenmeTest/1.0", "Accept": "application/json", "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7"})
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")
