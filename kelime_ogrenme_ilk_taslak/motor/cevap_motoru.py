from __future__ import annotations


class CevapMotoru:
    """Test ortamında araştırma verilerinden güvenli cevap adayları üretir."""

    async def generate(self, word, research, usage, sentences):
        contexts = usage.get("contexts", []) or []
        meanings = research.get("meanings", []) or []

        # Araştırma motoru ağ/sağlayıcı nedeniyle sonuç döndürmezse burada
        # IndexError vermek yerine pipeline'ın kalite kontrolüne bırak.
        if meanings:
            meaning = meanings[0]
            first_text = f'"{word}" için araştırma sonucu: {meaning}'
        else:
            first_text = (
                f'"{word}" için araştırma sonucu alınamadı; '
                "araştırma verisi yetersiz."
            )

        responses = [
            {
                "type": "bilgilendirici",
                "text": first_text,
                "basis": "web_research",
            },
            {
                "type": "ornekli",
                "text": (
                    f'"{word}" kelimesinin kullanımına ilişkin araştırma yapıldı. '
                    f"İncelenen bağlam sayısı: {len(contexts)}."
                ),
                "basis": "usage_research",
            },
        ]

        if sentences:
            first_sentence = sentences[0].get("sentence", "").strip()
            if first_sentence:
                responses.append({
                    "type": "ornek_cumleli",
                    "text": (
                        f'"{word}" için gerçek kullanım örneği araştırma sonucunda '
                        f"bulundu: {first_sentence}"
                    ),
                    "basis": "sentence_research",
                })

        return responses
