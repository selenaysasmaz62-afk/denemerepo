from datetime import datetime, timezone
import json


class SonucMotoru:
    def __init__(self, db):
        self.db = db

    async def save_validation(self, learning_id, validation):
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT INTO automatic_word_validation "
            "(learning_id, score, accepted, checks_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                learning_id,
                float(validation.get("score", 0)),
                1 if validation.get("accepted") else 0,
                json.dumps(validation.get("checks", {}), ensure_ascii=False),
                now,
            ),
        )

    async def save_test_result(self, learning_id, word, research, usage, sentences, responses, validation):
        await self.save_validation(learning_id, validation)
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "word": word,
            "research": research,
            "usage": usage,
            "sentences": sentences,
            "responses": responses,
            "validation": validation,
        }
        self.db.execute(
            "INSERT INTO automatic_word_results "
            "(learning_id, result_json, created_at) VALUES (?, ?, ?)",
            (learning_id, json.dumps(payload, ensure_ascii=False), now),
        )

    async def mark_failed(self, learning_id, validation):
        await self.save_validation(learning_id, validation)
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE automatic_word_learning SET status='failed', current_step='validation', updated_at=? WHERE id=?",
            (now, learning_id),
        )
