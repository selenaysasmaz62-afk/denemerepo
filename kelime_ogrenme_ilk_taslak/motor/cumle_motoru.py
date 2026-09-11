from __future__ import annotations

import re


class CumleMotoru:
    def __init__(self):
        pass

    async def research(self, word, research, usage):
        candidates = []
        seen = set()
        for text in usage.get("contexts", []):
            for sentence in re.split(r'(?<=[.!?])\s+', text):
                sentence = sentence.strip(" -–—\t")
                if len(sentence) < 20 or len(sentence) > 300:
                    continue
                if word.casefold() not in sentence.casefold():
                    continue
                key = " ".join(sentence.casefold().split())
                if key not in seen:
                    seen.add(key)
                    candidates.append({"sentence": sentence, "source": "web_research"})
        return candidates[:12]
