import asyncio
import tempfile
from pathlib import Path

from motor.analiz_motoru import AnalizMotoru
from motor.kalite_kontrol import KaliteKontrol
from motor.kuyruk_motoru import KelimeKuyrukMotoru
from veri.veritabani import TestDatabase


def test_analiz():
    assert AnalizMotoru().analyze(None)["status"] == "empty"
    assert AnalizMotoru().analyze(["a", "b"])["items"] == 2


def test_kalite():
    kontrol = KaliteKontrol(90)
    invalid = kontrol.validate("ince", {}, {}, [{"sentence": "incehesap.com"}], [])
    assert not invalid["accepted"]

    valid_sentences = [
        {"sentence": "Bu kumaş oldukça ince ve yumuşak.", "source": "tatoeba", "url": "https://tatoeba.org/"},
        {"sentence": "İnce bir yağmur akşam boyunca sürdü.", "source": "tatoeba", "url": "https://tatoeba.org/"},
        {"sentence": "Kalemle ince bir çizgi çizdi.", "source": "dictionary_example", "url": "https://api.dictionaryapi.dev/"},
    ]
    research = {
        "meanings": ["Birinci anlam açıklaması", "İkinci anlam açıklaması"],
        "senses": [{"definition": "Birinci anlam açıklaması"}, {"definition": "İkinci anlam açıklaması"}],
        "sources": [{"url": "a"}, {"url": "b"}],
    }
    usage = {"contexts": ["ince bir çizgi", "ince kumaş"]}
    responses = [{"text": "a"}, {"text": "b"}]
    valid = kontrol.validate("ince", research, usage, valid_sentences, responses)
    assert valid["accepted"]


def test_database_and_queue():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_file = root / "kelimeler.txt"
        input_file.write_text("ince\n\n# yorum\nkalın\n", encoding="utf-8")
        db = TestDatabase(root / "test.sqlite3")
        db.initialize()
        try:
            asyncio.run(KelimeKuyrukMotoru(input_file, db).enqueue_input_words())
            first = KelimeKuyrukMotoru(input_file, db).next_word()
            assert first and first["word"] == "ince"
        finally:
            db.close()


if __name__ == "__main__":
    test_analiz()
    test_kalite()
    test_database_and_queue()
    print("Sistem OK")
