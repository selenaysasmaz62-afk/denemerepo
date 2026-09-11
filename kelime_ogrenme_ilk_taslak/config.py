from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

@dataclass(frozen=True)
class Settings:
    input_file: Path = BASE_DIR / "giris" / "kelimeler.txt"
    db_file: Path = BASE_DIR / "test_db" / "kelime_ogrenme_test.db"
    min_quality_score: float = 90.0
    max_research_attempts: int = 3

SETTINGS = Settings()
