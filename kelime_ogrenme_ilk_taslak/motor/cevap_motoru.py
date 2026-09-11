from __future__ import annotations


class CevapMotoru:
    """Test ortamında, araştırılan kelime için güvenli cevap adayları üretir."""

    async def generate(self, word, research, usage, sentences):
        contexts = usage.get("contexts", [])
        meaning = research.get("meanings", [f'"{word}" kelimesinin kullanımı araştırıldı.'])[0]

        responses = [
            {
                "type": "bilgilendirici",
                "text": f'"{word}" için araştırma sonucu: {meaning}',
                "basis": "web_research",
            },
            {
                "type": "ornekli",
                "text": (
                    f'"{word}" kelimesinin kullanımına örnekler bulundu. '
                    f'İncelenen bağlam sayısı: {len(contexts)}.'
                ),
                "basis": "usage_research",
            },
        ]

        if sentences:
            responses.append({
                "type": "ornek_cumleli",
                "text": f'"{word}" için gerçek kullanım örneği araştırma sonucunda bulundu: {sentences[0]["sentence"]}',
                "basis": "sentence_research",
            })

        return responses
