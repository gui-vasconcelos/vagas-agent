import sqlite3
import os

class Database:
    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS seen_jobs (id TEXT PRIMARY KEY)")
        self.conn.commit()

    def is_seen(self, job_id):
        cursor = self.conn.execute("SELECT 1 FROM seen_jobs WHERE id = ?", (job_id,))
        return cursor.fetchone() is not None

    def add(self, job_id):
        self.conn.execute("INSERT OR IGNORE INTO seen_jobs (id) VALUES (?)", (job_id,))
        self.conn.commit()
