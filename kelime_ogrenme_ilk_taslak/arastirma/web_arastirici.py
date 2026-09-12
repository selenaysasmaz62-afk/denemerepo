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


class _BingSearchParser(HTMLParser):
    """Bing HTML sonuçlarını li.b_algo içindeki h2/p alanlarından toplar."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._in_result = False
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""
        self._li_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())

        if tag == "li" and "b_algo" in classes:
            self._finish_result()
            self._in_result = True
            self._li_depth = 1
            self._title = ""
            self._snippet = ""
            self._url = ""
            return

        if not self._in_result:
            return

        if tag == "li":
            self._li_depth += 1
        elif tag == "a" and self._li_depth >= 1 and not self._title:
            # Bing normalde başlığı li.b_algo > h2 > a altında verir.
            self._title_active = True
            self._url = html_lib.unescape(attrs_dict.get("href", ""))
        elif tag == "p" and self._li_depth >= 1:
            self._snippet_active = True

    def handle_endtag(self, tag):
        if not self._in_result:
            return
        if tag == "a" and self._title_active:
            self._title_active = False
        elif tag == "p" and self._snippet_active:
            self._snippet_active = False
        elif tag == "li":
            self._li_depth -= 1
            if self._li_depth <= 0:
                self._finish_result()

    def handle_data(self, data):
        if self._title_active:
            self._title += " " + data
        elif self._snippet_active:
            self._snippet += " " + data

    def close(self):
        super().close()
        self._finish_result()

    def _finish_result(self):
        if not self._in_result:
            return
        title = _HtmlSearchParser._clean(self._title)
        snippet = _HtmlSearchParser._clean(self._snippet)
        if title:
            self.results.append({"title": title, "snippet": snippet, "url": self._url})
        self._in_result = False
        self._title_active = False
        self._snippet_active = False
        self._title = ""
        self._snippet = ""
        self._url = ""
        self._li_depth = 0


class WebArastirici:
    """Anahtarsız, yedekli web araştırıcısı."""

    def __init__(self, timeout=12, max_results=8):
        self.timeout = timeout
        self.max_results = max_results

    async def search(self, query):
        return await asyncio.to_thread(self._search_sync, query)

    def _search_sync(self, query):
        errors = []
        for endpoint, parser_cls in (
            ("https://html.duckduckgo.com/html/", _HtmlSearchParser),
            ("https://lite.duckduckgo.com/lite/", _LiteSearchParser),
            ("https://www.bing.com/search", _BingSearchParser),
        ):
            try:
                if "bing.com" in endpoint:
                    url = endpoint + "?q=" + quote_plus(query) + "&setlang=tr"
                    html_text = self._fetch(url)
                else:
                    form = "q=" + quote_plus(query) + "&kl=tr-tr"
                    html_text = self._fetch(endpoint, data=form.encode("ascii"))
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

        try:
            api_url = (
                "https://api.duckduckgo.com/?q=" + quote_plus(query)
                + "&format=json&no_html=1&skip_disambig=0"
            )
            raw = self._fetch(api_url)
            payload = json.loads(raw)
            results = []
            heading = payload.get("Heading") or ""
            abstract = payload.get("AbstractText") or ""
            abstract_url = payload.get("AbstractURL") or ""
            if heading or abstract:
                results.append({"title": heading or query, "snippet": abstract, "url": abstract_url})
            for item in payload.get("RelatedTopics", [])[: self.max_results]:
                if not isinstance(item, dict):
                    continue
                text = item.get("Text") or ""
                first_url = item.get("FirstURL") or ""
                if text:
                    results.append({"title": query, "snippet": text, "url": first_url})
            results = self._normalize_results(results)
            if results:
                return {"query": query, "results": results, "error": None, "provider": "duckduckgo_api"}
            errors.append("instant_answer:no_results")
        except Exception as exc:
            errors.append(f"instant_answer:{exc}")

        return {"query": query, "results": [], "error": "; ".join(errors) or "no_results", "provider": None}

    def _fetch(self, url, data=None):
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        }
        if data is not None:
            headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": url,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
            })
        request = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _looks_like_challenge(text):
        lower = text.casefold()
        return (("captcha" in lower or "are you a human" in lower or "unusual traffic" in lower)
                and "result__a" not in lower and "result-link" not in lower and "b_algo" not in lower)

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
