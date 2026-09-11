from __future__ import annotations

from arastirma.web_arastirici import WebArastirici


class KelimeArastirmaMotoru:
    def __init__(self):
        self.web = WebArastirici()

    async def research(self, word):
        searches = [
            f'"{word}" Türkçe anlamı sözlük',
            f'"{word}" ne demek kullanım',
            f'"{word}" TDK',
        ]
        results = []
        seen = set()
        for query in searches:
            data = await self.web.search(query)
            for result in data.get("results", []):
                url = result.get("url", "")
                key = url or result.get("title", "")
                if key and key not in seen:
                    seen.add(key)
                    results.append(result)

        meanings = []
        for result in results:
            text = f'{result.get("title", "")} {result.get("snippet", "")}'.strip()
            if text:
                meanings.append(text)

        return {
            "word": word,
            "meanings": meanings[:12],
            "sources": results[:12],
        }

    async def research_usage(self, word, research):
        queries = [
            f'"{word}" örnek cümle',
            f'"{word}" günlük kullanım cümle',
            f'"{word}" haber kullanım',
            f'"{word}" kullanım örnekleri',
        ]
        contexts = []
        patterns = []
        seen = set()

        for query in queries:
            data = await self.web.search(query)
            for result in data.get("results", []):
                text = f'{result.get("title", "")} {result.get("snippet", "")}'.strip()
                key = " ".join(text.casefold().split())
                if text and key not in seen:
                    seen.add(key)
                    contexts.append(text)

        # Arama sağlayıcısı kullanım sorgularına sonuç vermezse, ilk araştırmanın
        # kaynak/snippet verisini ikinci bir kullanım kaynağı olarak değerlendir.
        if len(contexts) < 2:
            for result in research.get("sources", []) if isinstance(research, dict) else []:
                text = f'{result.get("title", "")} {result.get("snippet", "")}'.strip()
                key = " ".join(text.casefold().split())
                if text and key not in seen:
                    seen.add(key)
                    contexts.append(text)

        lower = word.casefold()
        for context in contexts:
            if lower in context.casefold():
                patterns.append(f'"{word}" kullanım bağlamı: {context}')

        return {
            "word": word,
            "contexts": contexts[:15],
            "patterns": patterns[:10],
        }
