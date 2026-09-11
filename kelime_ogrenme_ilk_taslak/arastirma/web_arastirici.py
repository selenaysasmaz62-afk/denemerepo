from __future__ import annotations

import asyncio
import re
from html.parser import HTMLParser
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


class _SearchParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._in_result = False
        self._in_title = False
        self._in_snippet = False
        self._title = ""
        self._snippet = ""
        self._url = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._in_result = True
            self._in_title = True
            self._title = ""
            self._url = attrs.get("href", "")
        elif tag in ("a", "div") and ("result__snippet" in classes or "result__body" in classes):
            self._in_snippet = True

    def handle_endtag(self, tag):
        if tag == "a" and self._in_title:
            self._in_title = False
        if tag == "div" and self._in_snippet:
            self._in_snippet = False
            if self._title or self._snippet:
                self.results.append({
                    "title": self._clean(self._title),
                    "snippet": self._clean(self._snippet),
                    "url": self._url,
                })
                self._title = self._snippet = self._url = ""
                self._in_result = False

    def handle_data(self, data):
        if self._in_title:
            self._title += " " + data
        elif self._in_snippet:
            self._snippet += " " + data

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
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FatosKelimeOgrenme/1.0)"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            return {"query": query, "results": [], "error": str(exc)}

        parser = _SearchParser()
        parser.feed(html)
        results = []
        seen = set()
        for item in parser.results:
            key = (item["title"], item["url"])
            if key in seen or not item["title"]:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= self.max_results:
                break
        return {"query": query, "results": results, "error": None}
