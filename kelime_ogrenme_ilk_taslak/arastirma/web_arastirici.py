from __future__ import annotations

import asyncio
import re
from html.parser import HTMLParser
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


class _SearchParser(HTMLParser):
    """DuckDuckGo HTML sonuçlarını JS gerektirmeden toplar."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())

        if tag == "a" and "result__a" in classes:
            self._finish_result()
            self._title_active = True
            self._title = ""
            self._snippet = ""
            self._url = attrs.get("href", "")
            return

        if "result__snippet" in classes or "result__body" in classes:
            self._snippet_active = True

    def handle_endtag(self, tag):
        if tag == "a" and self._title_active:
            self._title_active = False
        if tag in ("a", "div") and self._snippet_active:
            self._snippet_active = False

    def handle_data(self, data):
        if self._title_active:
            self._title += " " + data
        elif self._snippet_active:
            self._snippet += " " + data

    def close(self):
        super().close()
        self._finish_result()

    def _finish_result(self):
        title = self._clean(self._title)
        snippet = self._clean(self._snippet)
        if title:
            self.results.append({
                "title": title,
                "snippet": snippet,
                "url": self._url,
            })
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""

    @staticmethod
    def _clean(text):
        return re.sub(r"\s+", " ", text).strip()


class WebArastirici:
    """Anahtar kelime araştırması için hafif, anahtarsız web arayıcısı."""

    def __init__(self, timeout=12, max_results=8):
        self.timeout = timeout
        self.max_results = max_results

    async def search(self, query):
        return await asyncio.to_thread(self._search_sync, query)

    def _search_sync(self, query):
        url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 10) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                ),
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            return {"query": query, "results": [], "error": str(exc)}

        parser = _SearchParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            return {
                "query": query,
                "results": [],
                "error": f"parse_error: {exc}",
            }

        results = []
        seen = set()
        for item in parser.results:
            title = item["title"]
            url = item["url"]
            key = (title.casefold(), url)
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= self.max_results:
                break

        return {
            "query": query,
            "results": results,
            "error": None,
        }
