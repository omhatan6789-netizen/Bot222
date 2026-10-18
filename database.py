import os
import logging
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

log = logging.getLogger("Bot222.database")


def get_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise RuntimeError(
            "متغير DATABASE_URL غير موجود في إعدادات الاستضافة."
        )

    return psycopg2.connect(
        database_url,
        sslmode="require",
        connect_timeout=10,
        cursor_factory=RealDictCursor,
    )


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def init_db():
    """تأكد من اتصال قاعدة البيانات."""
    with db_cursor() as cur:
        cur.execute("SELECT 1")
    log.info("Supabase database connection successful")


def get_global_ranks(user_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT rank_key
            FROM public.global_ranks
            WHERE user_id = %s
            ORDER BY created_at
            """,
            (user_id,),
        )
        return [row["rank_key"] for row in cur.fetchall()]


def get_group_ranks(chat_id, user_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT rank_key
            FROM public.group_ranks
            WHERE chat_id = %s AND user_id = %s
            ORDER BY created_at
            """,
            (chat_id, user_id),
        )
        return [row["rank_key"] for row in cur.fetchall()]


def get_all_ranks(chat_id, user_id):
    return {
        "global": get_global_ranks(user_id),
        "group": get_group_ranks(chat_id, user_id),
    }


def grant_rank(chat_id, user_id, rank_key, granted_by=None, global_rank=False):
    if global_rank:
        if rank_key not in ("dev", "dev2"):
            raise ValueError("رتبة عالمية غير صالحة.")

        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.global_ranks
                    (user_id, rank_key, granted_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, rank_key) DO NOTHING
                """,
                (user_id, rank_key, granted_by),
            )
    else:
        if rank_key not in (
            "owner", "creator", "manager", "admin", "premium"
        ):
            raise ValueError("رتبة مجموعة غير صالحة.")

        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.group_ranks
                    (chat_id, user_id, rank_key, granted_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id, user_id, rank_key) DO NOTHING
                """,
                (chat_id, user_id, rank_key, granted_by),
            )


def revoke_rank(chat_id, user_id, rank_key, global_rank=False):
    if global_rank:
        with db_cursor() as cur:
            cur.execute(
                """
                DELETE FROM public.global_ranks
                WHERE user_id = %s AND rank_key = %s
                """,
                (user_id, rank_key),
            )
    else:
        with db_cursor() as cur:
            cur.execute(
                """
                DELETE FROM public.group_ranks
                WHERE chat_id = %s
                  AND user_id = %s
                  AND rank_key = %s
                """,
                (chat_id, user_id, rank_key),
            )


def revoke_all_ranks(chat_id, user_id, global_rank=False):
    if global_rank:
        with db_cursor() as cur:
            cur.execute(
                "DELETE FROM public.global_ranks WHERE user_id = %s",
                (user_id,),
            )
    else:
        with db_cursor() as cur:
            cur.execute(
                """
                DELETE FROM public.group_ranks
                WHERE chat_id = %s AND user_id = %s
                """,
                (chat_id, user_id),
            )


def save_group_member(chat_id, user_id, first_name="", username=None):
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.group_members
                (chat_id, user_id, first_name, username)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (chat_id, user_id)
            DO UPDATE SET
                first_name = EXCLUDED.first_name,
                username = EXCLUDED.username
            """,
            (chat_id, user_id, first_name or "", username),
        )


def get_group_members(chat_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT user_id, first_name, username
            FROM public.group_members
            WHERE chat_id = %s
            ORDER BY first_name
            """,
            (chat_id,),
        )
        return cur.fetchall()


def list_group_rank_holders(chat_id, rank_key):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT user_id, first_name, username
            FROM public.group_members
            WHERE chat_id = %s
              AND user_id IN (
                  SELECT user_id
                  FROM public.group_ranks
                  WHERE chat_id = %s AND rank_key = %s
              )
            ORDER BY first_name
            """,
            (chat_id, chat_id, rank_key),
        )
        return cur.fetchall()
