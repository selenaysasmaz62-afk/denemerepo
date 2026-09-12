from __future__ import annotations

import json
from urllib.parse import quote_plus

from .cumle_motoru_v2 import CumleMotoruV2


_original_tatoeba_sentences = CumleMotoruV2._tatoeba_sentences


async def _tatoeba_sentences_with_paging(self, word):
    """Tatoeba v1 relevance ilk sayfada eşleşme vermezse sonraki sayfaları tara."""
    values = await _original_tatoeba_sentences(self, word)
    if values:
        return values

    seen = set()
    for page in range(2, 6):
        url = (
            "https://api.tatoeba.org/v1/sentences?"
            f"lang=tur&q={quote_plus(word)}"
            "&word_count=3-&is_orphan=no&is_unapproved=no"
            "&sort=relevance&limit=50"
            f"&page={page}"
        )
        try:
            raw = await self._fetch_url_text(url)
            payload = json.loads(raw)
            items = payload.get("data", []) if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                text = self._clean_text(item.get("text") or item.get("sentence") or "")
                if not text or not self._contains_target_word(word, text):
                    continue
                if len(text.split()) < 3:
                    continue
                key = " ".join(text.casefold().split())
                if key in seen:
                    continue
                seen.add(key)
                sentence_id = item.get("id")
                source_url = (
                    f"https://tatoeba.org/en/sentences/show/{sentence_id}"
                    if sentence_id else "https://api.tatoeba.org/"
                )
                values.append((text, source_url))
                if len(values) >= 15:
                    return values[:15]
        except Exception:
            continue

    return values[:15]


CumleMotoruV2._tatoeba_sentences = _tatoeba_sentences_with_paging
