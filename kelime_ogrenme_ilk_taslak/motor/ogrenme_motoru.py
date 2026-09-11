from config import SETTINGS
from veri.veritabani import TestDatabase
from motor.kuyruk_motoru import KelimeKuyrukMotoru
from motor.durum_motoru import DurumMotoru
from motor.arastirma_motoru import KelimeArastirmaMotoru
from motor.cumle_motoru_v2 import CumleMotoruV2
from motor.cevap_motoru import CevapMotoru
from motor.kalite_kontrol import KaliteKontrol
from motor.sonuc_motoru import SonucMotoru


class KelimeOgrenmeMotoru:
    def __init__(self):
        self.db = TestDatabase(SETTINGS.db_file)
        self.queue = KelimeKuyrukMotoru(SETTINGS.input_file, self.db)
        self.state = DurumMotoru(self.db)
        self.research = KelimeArastirmaMotoru()
        self.sentences = CumleMotoruV2()
        self.responses = CevapMotoru()
        self.quality = KaliteKontrol(SETTINGS.min_quality_score)
        self.results = SonucMotoru(self.db)

    async def run(self):
        self.db.initialize()
        await self.queue.enqueue_input_words()
        while True:
            item = self.queue.next_word()
            if not item:
                break
            await self.process_word(item["id"], item["word"])

    @staticmethod
    def _normalize_usage(word, usage):
        if isinstance(usage, dict):
            return {
                "word": usage.get("word", word),
                "contexts": usage.get("contexts", []) or [],
                "patterns": usage.get("patterns", []) or [],
            }
        if isinstance(usage, list):
            contexts, seen = [], set()
            for item in usage:
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = str(item.get("snippet") or item.get("text") or item.get("title") or "").strip()
                else:
                    text = str(item).strip()
                if text and text.casefold() not in seen:
                    seen.add(text.casefold())
                    contexts.append(text)
            return {
                "word": word,
                "contexts": contexts,
                "patterns": [
                    f'"{word}" kullanım bağlamı: {text}'
                    for text in contexts
                    if word.casefold() in text.casefold()
                ][:10],
            }
        return {"word": word, "contexts": [], "patterns": []}

    async def process_word(self, learning_id, word):
        await self.state.set_step(learning_id, "researching")
        research = await self.research.research(word)
        await self.state.save_data(learning_id, "research", research)

        await self.state.set_step(learning_id, "usage_research")
        usage = await self.research.research_usage(word, research)
        usage = self._normalize_usage(word, usage)
        await self.state.save_data(learning_id, "usage", usage)

        await self.state.set_step(learning_id, "sentence_research")
        sentences = await self.sentences.research(word, research, usage)
        await self.state.save_data(learning_id, "sentences", sentences)

        await self.state.set_step(learning_id, "response_generation")
        responses = await self.responses.generate(word, research, usage, sentences)
        await self.state.save_data(learning_id, "responses", responses)

        await self.state.set_step(learning_id, "validation")
        validation = self.quality.validate(word, research, usage, sentences, responses)
        if not validation["accepted"]:
            await self.results.mark_failed(learning_id, validation)
            return

        await self.state.set_step(learning_id, "test_result_saved")
        await self.results.save_test_result(
            learning_id, word, research, usage, sentences, responses, validation
        )
        await self.state.set_step(learning_id, "completed")
