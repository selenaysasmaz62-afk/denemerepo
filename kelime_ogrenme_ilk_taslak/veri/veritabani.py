import json
import sqlite3
from pathlib import Path


class TestDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self.conn = None

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.conn is not None:
            self.close()
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
            sentences_json TEXT,
            responses_json TEXT,
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

        columns = {
            row[1] for row in self.conn.execute(
                "PRAGMA table_info(automatic_word_research)"
            ).fetchall()
        }
        for column in ("sentences_json", "responses_json"):
            if column not in columns:
                self.conn.execute(
                    f"ALTER TABLE automatic_word_research ADD COLUMN {column} TEXT"
                )
        self.commit()

    def execute(self, sql, params=()):
        if self.conn is None:
            raise RuntimeError("Veritabanı başlatılmadı.")
        cur = self.conn.execute(sql, params)
        self.commit()
        return cur

    def fetchone(self, sql, params=()):
        if self.conn is None:
            raise RuntimeError("Veritabanı başlatılmadı.")
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def save_json(self, learning_id, data_type, data):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = json.dumps(data, ensure_ascii=False)
        columns = {
            "research": "research_json",
            "usage": "usage_json",
            "sentences": "sentences_json",
            "responses": "responses_json",
        }
        column = columns.get(data_type)
        if not column:
            raise ValueError(f"Bilinmeyen veri tipi: {data_type}")

        row = self.fetchone(
            "SELECT learning_id FROM automatic_word_research WHERE learning_id=?",
            (learning_id,)
        )
        if not row:
            values = {
                "research_json": None,
                "usage_json": None,
                "sentences_json": None,
                "responses_json": None,
            }
            values[column] = payload
            self.execute(
                "INSERT INTO automatic_word_research "
                "(learning_id, research_json, usage_json, sentences_json, responses_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (learning_id, values["research_json"], values["usage_json"],
                 values["sentences_json"], values["responses_json"], now, now)
            )
        else:
            self.execute(
                f"UPDATE automatic_word_research SET {column}=?, updated_at=? WHERE learning_id=?",
                (payload, now, learning_id)
            )

    def commit(self):
        if self.conn is not None:
            self.conn.commit()

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
