from __future__ import annotations

import asyncio
import html as html_lib
import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen


class _HtmlSearchParser(HTMLParser):
    """DuckDuckGo HTML sonuçlarını HTML yapısından bağımsız toplar."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())

        if tag == "a" and "result__a" in classes:
            self._finish_result()
            self._title_active = True
            self._title = ""
            self._snippet = ""
            self._url = self._decode_url(attrs_dict.get("href", ""))
            return

        if "result__snippet" in classes:
            self._snippet_active = True

    def handle_endtag(self, tag):
        # Snippetler çoğu zaman <a> içinde küçük <b>/<span> etiketleri
        # barındırır. Bu nedenle sadece div kapanışında kapat.
        if tag == "div" and self._snippet_active:
            self._snippet_active = False
        if tag == "a" and self._title_active:
            self._title_active = False

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
            self.results.append({"title": title, "snippet": snippet, "url": self._url})
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""

    @staticmethod
    def _decode_url(url):
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        parsed = urlparse(url)
        if parsed.path.startswith("/l/") or "uddg" in parse_qs(parsed.query):
            target = parse_qs(parsed.query).get("uddg")
            if target:
                return unquote(target[0])
        return html_lib.unescape(url)

    @staticmethod
    def _clean(text):
        text = html_lib.unescape(text)
        return re.sub(r"\s+", " ", text).strip()


class _LiteSearchParser(HTMLParser):
    """DuckDuckGo Lite sonuçlarını toplar."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())
        href = attrs_dict.get("href", "")

        if tag == "a" and "result-link" in classes:
            self._finish_result()
            self._title_active = True
            self._title = ""
            self._snippet = ""
            self._url = _HtmlSearchParser._decode_url(href)
        elif "result-snippet" in classes:
            self._snippet_active = True

    def handle_endtag(self, tag):
        if tag == "a" and self._title_active:
            self._title_active = False
        if tag in ("td", "div") and self._snippet_active:
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
        title = _HtmlSearchParser._clean(self._title)
        snippet = _HtmlSearchParser._clean(self._snippet)
        if title:
            self.results.append({"title": title, "snippet": snippet, "url": self._url})
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""


class WebArastirici:
    """Anahtarsız, yedekli web araştırıcısı.

    Sıra:
      1) DuckDuckGo HTML
      2) DuckDuckGo Lite
      3) DuckDuckGo Instant Answer API
    Bir sağlayıcı sonuç vermezse diğeri denenir.
    """

    def __init__(self, timeout=12, max_results=8):
        self.timeout = timeout
        self.max_results = max_results

    async def search(self, query):
        return await asyncio.to_thread(self._search_sync, query)

    def _search_sync(self, query):
        errors = []

        for endpoint, parser_cls in (
            (
                "https://html.duckduckgo.com/html/?q="
                + quote_plus(query)
                + "&kl=tr-tr",
                _HtmlSearchParser,
            ),
            (
                "https://lite.duckduckgo.com/lite/?q="
                + quote_plus(query)
                + "&kl=tr-tr",
                _LiteSearchParser,
            ),
        ):
            try:
                html_text = self._fetch(endpoint)
                if self._looks_like_challenge(html_text):
                    errors.append(f"anti_bot:{endpoint.split('/')[2]}")
                    continue

                parser = parser_cls()
                parser.feed(html_text)
                parser.close()
                results = self._normalize_results(parser.results)
                if results:
                    return {"query": query, "results": results, "error": None, "provider": endpoint}
                errors.append(f"no_results:{endpoint.split('/')[2]}")
            except Exception as exc:
                errors.append(f"{endpoint.split('/')[2]}:{exc}")

        # Son çare: DDG Instant Answer. Özellikle tek kelimelerde anlam/
        # açıklama sağlayabilir; genel web sonucu kadar zengin değildir.
        try:
            api_url = (
                "https://api.duckduckgo.com/?q="
                + quote_plus(query)
                + "&format=json&no_html=1&skip_disambig=0"
            )
            raw = self._fetch(api_url)
            payload = json.loads(raw)
            results = []
            heading = payload.get("Heading") or ""
            abstract = payload.get("AbstractText") or ""
            abstract_url = payload.get("AbstractURL") or ""
            if heading or abstract:
                results.append({
                    "title": heading or query,
                    "snippet": abstract,
                    "url": abstract_url,
                })

            for item in payload.get("RelatedTopics", [])[: self.max_results]:
                if not isinstance(item, dict):
                    continue
                text = item.get("Text") or ""
                first_url = item.get("FirstURL") or ""
                if text:
                    results.append({
                        "title": query,
                        "snippet": text,
                        "url": first_url,
                    })

            results = self._normalize_results(results)
            if results:
                return {"query": query, "results": results, "error": None, "provider": "duckduckgo_api"}
            errors.append("instant_answer:no_results")
        except Exception as exc:
            errors.append(f"instant_answer:{exc}")

        return {
            "query": query,
            "results": [],
            "error": "; ".join(errors) or "no_results",
            "provider": None,
        }

    def _fetch(self, url):
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"
                ),
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _looks_like_challenge(text):
        lower = text.casefold()
        return (
            ("captcha" in lower or "are you a human" in lower or "unusual traffic" in lower)
            and "result__a" not in lower
            and "result-link" not in lower
        )

    def _normalize_results(self, items):
        results = []
        seen = set()
        for item in items:
            title = _HtmlSearchParser._clean(item.get("title", ""))
            snippet = _HtmlSearchParser._clean(item.get("snippet", ""))
            url = item.get("url", "") or ""
            if not title:
                continue
            key = (title.casefold(), url)
            if key in seen:
                continue
            seen.add(key)
            results.append({"title": title, "snippet": snippet, "url": url})
            if len(results) >= self.max_results:
                break
        return results
