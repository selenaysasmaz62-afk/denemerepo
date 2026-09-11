import json
import sqlite3
from pathlib import Path

class TestDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self.conn = None

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS automatic_word_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            normalized_word TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT NOT NULL DEFAULT 'queued',
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS automatic_word_learning_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            learning_id INTEGER NOT NULL,
            step TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS automatic_word_research (
            learning_id INTEGER PRIMARY KEY,
            research_json TEXT,
            usage_json TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS automatic_word_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            learning_id INTEGER NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS automatic_word_validation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            learning_id INTEGER NOT NULL,
            score REAL NOT NULL,
            accepted INTEGER NOT NULL,
            checks_json TEXT,
            created_at TEXT NOT NULL
        );
        ''')
        self.commit()

    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.commit()
        return cur

    def fetchone(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def save_json(self, learning_id, data_type, data):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        row = self.fetchone(
            "SELECT learning_id FROM automatic_word_research WHERE learning_id=?",
            (learning_id,)
        )
        payload = json.dumps(data, ensure_ascii=False)
        if not row:
            self.execute(
                "INSERT INTO automatic_word_research "
                "(learning_id, research_json, usage_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (learning_id, payload if data_type == "research" else None,
                 payload if data_type == "usage" else None, now, now)
            )
        else:
            column = "research_json" if data_type == "research" else "usage_json"
            self.execute(
                f"UPDATE automatic_word_research SET {column}=?, updated_at=? WHERE learning_id=?",
                (payload, now, learning_id)
            )

    def commit(self):
        self.conn.commit()
