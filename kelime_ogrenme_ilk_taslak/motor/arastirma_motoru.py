from __future__ import annotations

import asyncio
import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici


class KelimeArastirmaMotoru:
    """Kelime anlamlarını ve kullanımlarını birden fazla kaynaktan toplar."""

    _JUNK_TITLE = (
        "numaralı adam", "gizli yüz", "iskeleti", "tanıma sistemi",
        "film", "albüm", "şarkı", "oyun", "dizi", "bölüm",
    )

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=8)

    async def research(self, word):
        results = []
        seen = set()

        # Genel aramayı tek sorguya bırakmıyoruz. Özellikle çok anlamlı
        # kelimelerde sözlük/anlam sonuçlarını ayrı ayrı topluyoruz.
        queries = (
            f'"{word}" TDK anlamı',
            f'"{word}" ne demek Türkçe',
            f'"{word}" sözlük anlamı',
            f'"{word}" kullanım Türkçe',
        )
        for query in queries:
            data = await self.web.search(query)
            self._append_results(results, seen, data.get("results", []))
            if len(results) >= 16:
                break

        dictionary = await self._dictionary_results(word)
        self._append_results(results, seen, dictionary)

        if len(results) < 4:
            wikipedia = await self._wikipedia_results(word)
            self._append_results(results, seen, wikipedia)

        ranked = sorted(results, key=lambda item: self._result_score(word, item), reverse=True)
        senses = self._build_senses(word, ranked)
        meanings = [sense["definition"] for sense in senses]

        return {
            "word": word,
            "senses": senses,
            "meanings": meanings[:12],
            "sources": ranked[:12],
        }

    async def research_usage(self, word, research):
        contexts = []
        patterns = []
        seen = set()

        queries = (
            f'"{word}" örnek cümle',
            f'"{word}" cümle içinde kullanım',
            f'"{word}" günlük kullanım örnekleri',
        )
        for query in queries:
            data = await self.web.search(query)
            self._append_contexts(contexts, seen, data.get("results", []))
            if len(contexts) >= 12:
                break

        if len(contexts) < 4:
            self._append_contexts(
                contexts,
                seen,
                research.get("sources", []) if isinstance(research, dict) else [],
            )

        lower = word.casefold()
        for context in contexts:
            if lower in context.casefold():
                patterns.append(f'"{word}" kullanım bağlamı: {context}')

        return {
            "word": word,
            "contexts": contexts[:15],
            "patterns": patterns[:10],
        }

    @classmethod
    def _result_score(cls, word, result):
        title = cls._clean_text(result.get("title", "")).casefold()
        snippet = cls._clean_text(result.get("snippet", "")).casefold()
        text = f"{title} {snippet}"
        score = 0

        if word.casefold() in title:
            score += 3
        for marker in ("tdk", "sözlük", "anlamı", "ne demek", "tanım", "dictionary"):
            if marker in text:
                score += 4
        if "wikipedia" in title:
            score += 1
        if any(marker in title for marker in cls._JUNK_TITLE):
            score -= 10
        if len(snippet) >= 40:
            score += 2
        if result.get("url"):
            score += 1
        return score

    @classmethod
    def _build_senses(cls, word, results):
        senses = []
        seen = set()
        for result in results:
            title = cls._clean_text(result.get("title", ""))
            snippet = cls._clean_text(result.get("snippet", ""))
            if not snippet:
                continue
            if any(marker in title.casefold() for marker in cls._JUNK_TITLE):
                continue

            definition = snippet
            definition = re.sub(r"^(?:anlamı|tanımı|sözlük anlamı)\s*[:\-]\s*", "", definition, flags=re.I)
            definition = cls._clean_text(definition)
            key = definition.casefold()
            if len(definition) < 20 or key in seen:
                continue
            seen.add(key)
            senses.append({
                "definition": definition,
                "part_of_speech": cls._guess_part_of_speech(definition),
                "source_title": title,
                "source_url": result.get("url", "") or "",
            })
            if len(senses) >= 8:
                break
        return senses

    @staticmethod
    def _guess_part_of_speech(text):
        lower = text.casefold()
        if any(x in lower for x in ("fiil", "eylem", "-mek", "-mak")):
            return "fiil"
        if "sıfat" in lower:
            return "sıfat"
        if "zarf" in lower:
            return "zarf"
        if "isim" in lower or "ad " in lower:
            return "isim"
        return "belirsiz"

    @staticmethod
    def _clean_text(value):
        return " ".join(html.unescape(str(value or "")).split()).strip()

    @staticmethod
    def _append_results(results, seen, items):
        for result in items:
            if not isinstance(result, dict):
                continue
            clean = {
                "title": KelimeArastirmaMotoru._clean_text(result.get("title", "")),
                "snippet": KelimeArastirmaMotoru._clean_text(result.get("snippet", "")),
                "url": result.get("url", "") or "",
            }
            key = clean["url"] or f'{clean["title"]}|{clean["snippet"]}'
            if key and key not in seen:
                seen.add(key)
                results.append(clean)

    @staticmethod
    def _append_contexts(contexts, seen, items):
        for result in items:
            if isinstance(result, str):
                text = KelimeArastirmaMotoru._clean_text(result)
            elif isinstance(result, dict):
                snippet = KelimeArastirmaMotoru._clean_text(result.get("snippet", ""))
                title = KelimeArastirmaMotoru._clean_text(result.get("title", ""))
                text = snippet or title
            else:
                continue
            key = " ".join(text.casefold().split())
            if text and key not in seen:
                seen.add(key)
                contexts.append(text)

    async def _dictionary_results(self, word):
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/tr/{quote_plus(word)}"
            payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
            results = []
            for entry in payload if isinstance(payload, list) else []:
                for meaning in entry.get("meanings", []):
                    pos = meaning.get("partOfSpeech", "")
                    for definition in meaning.get("definitions", []):
                        text = self._clean_text(definition.get("definition", ""))
                        example = self._clean_text(definition.get("example", ""))
                        if not text:
                            continue
                        snippet = f"{pos}: {text}" if pos else text
                        if example:
                            snippet += f" Örnek: {example}"
                        results.append({
                            "title": f"Dictionary API — {word}",
                            "snippet": snippet,
                            "url": "https://api.dictionaryapi.dev/",
                        })
            return results[:8]
        except Exception:
            return []

    async def _wikipedia_results(self, word):
        try:
            url = (
                "https://tr.wikipedia.org/w/api.php?action=query&list=search"
                f"&srsearch={quote_plus(word)}&format=json&utf8=1&srlimit=5"
            )
            payload = json.loads(await asyncio.to_thread(self._fetch_json, url))
            results = []
            for item in payload.get("query", {}).get("search", []):
                title = self._clean_text(item.get("title", ""))
                snippet = self._clean_text(item.get("snippet", "") or "")
                if title or snippet:
                    results.append({
                        "title": f"Vikipedi — {title or word}",
                        "snippet": snippet,
                        "url": (
                            f"https://tr.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}"
                            if title else "https://tr.wikipedia.org/"
                        ),
                    })
            return results
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
