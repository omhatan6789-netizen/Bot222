
import os
import sqlite3
from contextlib import contextmanager

SQLITE_PATH = os.getenv("SQLITE_PATH", "bot.sqlite3")


@contextmanager
def connection():
    folder = os.path.dirname(os.path.abspath(SQLITE_PATH))
    os.makedirs(folder, exist_ok=True)

    conn = sqlite3.connect(SQLITE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connection() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS global_ranks (
                user_id INTEGER NOT NULL,
                rank_key TEXT NOT NULL,
                granted_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, rank_key)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS group_ranks (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rank_key TEXT NOT NULL,
                granted_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, user_id, rank_key)
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_ranks_chat_rank
            ON group_ranks (chat_id, rank_key)
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                first_name TEXT NOT NULL DEFAULT '',
                username TEXT,
                PRIMARY KEY (chat_id, user_id)
            )
        """)


def get_global_ranks(user_id):
    with connection() as c:
        rows = c.execute(
            "SELECT rank_key FROM global_ranks WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return {row["rank_key"] for row in rows}


def get_group_ranks(chat_id, user_id):
    with connection() as c:
        rows = c.execute(
            """SELECT rank_key FROM group_ranks
               WHERE chat_id = ? AND user_id = ?""",
            (chat_id, user_id)
        ).fetchall()
        return {row["rank_key"] for row in rows}


def get_all_ranks(chat_id, user_id):
    return (
        get_global_ranks(user_id)
        | get_group_ranks(chat_id, user_id)
    )


def grant_rank(chat_id, user_id, rank_key, granted_by):
    with connection() as c:
        if rank_key in {"dev", "dev2"}:
            c.execute(
                """INSERT OR IGNORE INTO global_ranks
                   (user_id, rank_key, granted_by)
                   VALUES (?, ?, ?)""",
                (user_id, rank_key, granted_by)
            )
        elif rank_key != "member":
            c.execute(
                """INSERT OR IGNORE INTO group_ranks
                   (chat_id, user_id, rank_key, granted_by)
                   VALUES (?, ?, ?, ?)""",
                (chat_id, user_id, rank_key, granted_by)
            )


def revoke_rank(chat_id, user_id, rank_key):
    with connection() as c:
        if rank_key in {"dev", "dev2"}:
            c.execute(
                "DELETE FROM global_ranks WHERE user_id = ? AND rank_key = ?",
                (user_id, rank_key)
            )
        else:
            c.execute(
                """DELETE FROM group_ranks
                   WHERE chat_id = ? AND user_id = ? AND rank_key = ?""",
                (chat_id, user_id, rank_key)
            )


def revoke_all_ranks(chat_id, user_id, rank_keys):
    with connection() as c:
        for rank_key in rank_keys:
            if rank_key in {"dev", "dev2"}:
                c.execute(
                    "DELETE FROM global_ranks WHERE user_id = ? AND rank_key = ?",
                    (user_id, rank_key)
                )
            elif rank_key not in {"nawaf", "member"}:
                c.execute(
                    """DELETE FROM group_ranks
                       WHERE chat_id = ? AND user_id = ? AND rank_key = ?""",
                    (chat_id, user_id, rank_key)
                )


def save_group_member(chat_id, user_id, first_name, username):
    with connection() as c:
        c.execute(
            """INSERT INTO group_members
               (chat_id, user_id, first_name, username)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(chat_id, user_id) DO UPDATE SET
               first_name = excluded.first_name,
               username = excluded.username""",
            (chat_id, user_id, first_name or "", username)
        )


def get_group_members(chat_id):
    with connection() as c:
        return c.execute(
            """SELECT user_id, first_name, username
               FROM group_members WHERE chat_id = ?""",
            (chat_id,)
        ).fetchall()


def list_group_rank_holders(chat_id, rank_key):
    with connection() as c:
        if rank_key in {"dev", "dev2"}:
            rows = c.execute(
                """SELECT user_id FROM global_ranks
                   WHERE rank_key = ? ORDER BY user_id""",
                (rank_key,)
            ).fetchall()
        else:
            rows = c.execute(
                """SELECT user_id FROM group_ranks
                   WHERE chat_id = ? AND rank_key = ?
                   ORDER BY user_id""",
                (chat_id, rank_key)
            ).fetchall()

        return [row["user_id"] for row in rows]
