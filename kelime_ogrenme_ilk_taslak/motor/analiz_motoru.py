from __future__ import annotations


class AnalizMotoru:
    """Pipeline verileri için basit, deterministik analiz yardımcıları."""

    def analyze(self, value):
        if value is None:
            return {"value": None, "status": "empty", "items": 0, "text_length": 0}

        if isinstance(value, dict):
            items = len(value)
            text = " ".join(str(v) for v in value.values() if isinstance(v, str))
        elif isinstance(value, (list, tuple, set)):
            items = len(value)
            text = " ".join(str(v) for v in value)
        else:
            items = 1
            text = str(value)

        text_length = len(text.strip())
        return {
            "value": value,
            "status": "ready" if items and text_length else "empty",
            "items": items,
            "text_length": text_length,
        }
