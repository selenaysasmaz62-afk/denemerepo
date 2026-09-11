from datetime import datetime, timezone

class DurumMotoru:
    def __init__(self, db):
        self.db = db

    async def set_step(self, learning_id, step):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE automatic_word_learning SET current_step=?, status=?, updated_at=? WHERE id=?",
            (step, step, now, learning_id)
        )
        self.db.execute(
            "INSERT INTO automatic_word_learning_steps "
            "(learning_id, step, status, started_at) VALUES (?, ?, ?, ?)",
            (learning_id, step, "started", now)
        )

    async def save_data(self, learning_id, data_type, data):
        self.db.save_json(learning_id, data_type, data)
