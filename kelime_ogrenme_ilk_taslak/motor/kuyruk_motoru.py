from datetime import datetime, timezone

class KelimeKuyrukMotoru:
    def __init__(self, input_file, db):
        self.input_file = input_file
        self.db = db

    async def enqueue_input_words(self):
        if not self.input_file.exists():
            return
        now = datetime.now(timezone.utc).isoformat()
        for raw in self.input_file.read_text(encoding="utf-8").splitlines():
            word = raw.strip()
            if not word or word.startswith("#"):
                continue
            normalized = " ".join(word.casefold().split())
            self.db.execute(
                "INSERT OR IGNORE INTO automatic_word_learning "
                "(word, normalized_word, status, current_step, retry_count, created_at, updated_at) "
                "VALUES (?, ?, 'pending', 'queued', 0, ?, ?)",
                (word, normalized, now, now)
            )

    def next_word(self):
        return self.db.fetchone(
            "SELECT id, word FROM automatic_word_learning "
            "WHERE status IN ('pending','queued') ORDER BY id LIMIT 1"
        )
