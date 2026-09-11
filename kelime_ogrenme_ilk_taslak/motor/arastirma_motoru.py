from __future__ import annotations

import asyncio
import html
import json
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from arastirma.web_arastirici import WebArastirici


class KelimeArastirmaMotoru:
    """Kelime anlamı ve kullanımını araştırır."""

    def __init__(self):
        self.web = WebArastirici(timeout=12, max_results=8)

    async def research(self, word):
        results = []
        seen = set()

        query = f'"{word}" Türkçe anlamı kullanım sözlük'
        data = await self.web.search(query)
        self._append_results(results, seen, data.get("results", []))

        if len(results) < 2:
            dictionary = await self._dictionary_results(word)
            self._append_results(results, seen, dictionary)

        if len(results) < 2:
            wikipedia = await self._wikipedia_results(word)
            self._append_results(results, seen, wikipedia)

        meanings = []
        for result in results:
            title = self._clean_text(result.get("title", ""))
            snippet = self._clean_text(result.get("snippet", ""))
            text = f"{title} — {snippet}" if title and snippet else title or snippet
            if text:
                meanings.append(text)

        return {
            "word": word,
            "meanings": meanings[:12],
            "sources": results[:12],
        }

    async def research_usage(self, word, research):
        contexts = []
        patterns = []
        seen = set()

        query = f'"{word}" örnek cümle kullanım örnekleri'
        data = await self.web.search(query)
        self._append_contexts(contexts, seen, data.get("results", []))

        if len(contexts) < 2:
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
            key = clean["url"] or clean["title"]
            if key and key not in seen:
                seen.add(key)
                results.append(clean)

    @staticmethod
    def _append_contexts(contexts, seen, items):
        for result in items:
            if isinstance(result, str):
                text = KelimeArastirmaMotoru._clean_text(result)
            elif isinstance(result, dict):
                # Başlığı cümleye katma; aksi halde kaynak başlığı cümlenin başında tekrar eder.
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
                snippet = html.unescape(item.get("snippet", "") or "")
                snippet = self._clean_text(snippet)
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
