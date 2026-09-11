class Repository:
    def __init__(self, db):
        self.db = db

    def get_learning(self, learning_id):
        return self.db.fetchone(
            "SELECT * FROM automatic_word_learning WHERE id=?", (learning_id,)
        )
