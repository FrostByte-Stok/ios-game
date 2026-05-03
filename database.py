import sqlite3
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_file: str = "frostbyte.db"):
        self.db_file = db_file
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_file)

    def _init_db(self):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                status TEXT DEFAULT 'pending',
                experience TEXT,
                source TEXT,
                hours_per_day TEXT,
                percent INTEGER DEFAULT 60,
                total_logs INTEGER DEFAULT 0,
                total_profit INTEGER DEFAULT 0,
                worker_username TEXT DEFAULT '',
                created_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_profit INTEGER DEFAULT 0,
                total_logs INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_working INTEGER DEFAULT 1
            )
        ''')

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN worker_username TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        cursor.execute("INSERT OR IGNORE INTO project_stats (id) VALUES (1)")
        cursor.execute("INSERT OR IGNORE INTO work_status (id, is_working) VALUES (1, 1)")

        conn.commit()
        conn.close()

    def add_user(self, user_id: int, username: str):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, created_at) VALUES (?, ?, datetime('now'))",
            (user_id, username)
        )
        conn.commit()
        conn.close()

    def update_user_field(self, user_id: int, field: str, value: Any):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()
        conn.close()

    def update_worker_username(self, user_id: int, worker_username: str):
        self.update_user_field(user_id, 'worker_username', worker_username)

    def get_user(self, user_id: int) -> Optional[Dict]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_approved_users(self) -> List[Dict]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE status = 'approved' ORDER BY user_id")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_users(self) -> List[Dict]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE status IN ('approved', 'blocked') ORDER BY user_id")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_stats(self) -> Dict:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_stats WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {"total_profit": 0, "total_logs": 0}

    def update_stats(self, profit: int = 0, logs: int = 0):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE project_stats SET total_profit = total_profit + ?, total_logs = total_logs + ? WHERE id = 1",
            (profit, logs)
        )
        conn.commit()
        conn.close()

    def get_work_status(self) -> bool:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT is_working FROM work_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        return bool(row[0]) if row else True

    def set_work_status(self, status: bool):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE work_status SET is_working = ? WHERE id = 1", (1 if status else 0,))
        conn.commit()
        conn.close()
