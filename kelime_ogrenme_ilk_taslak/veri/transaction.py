class Transaction:
    def __init__(self, db):
        self.db = db
    def __enter__(self):
        self.db.conn.execute("BEGIN")
        return self.db
    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.db.conn.rollback()
        else:
            self.db.conn.commit()
