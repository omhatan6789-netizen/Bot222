import os
import psycopg2
from psycopg2.extras import RealDictCursor


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        raise RuntimeError(
            "متغير DATABASE_URL غير مضبوط في إعدادات الاستضافة."
        )

    return psycopg2.connect(
        url,
        connect_timeout=8,
        sslmode=os.getenv("PGSSLMODE", "require"),
        cursor_factory=RealDictCursor,
    )


def upsert_user(user):
    if not user or user.is_bot:
        return

    conn = _connect()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.bot_users
                        (user_id, first_name, username)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        username = EXCLUDED.username,
                        updated_at = NOW()
                    """,
                    (
                        user.id,
                        user.first_name or "",
                        user.username,
                    ),
                )
    finally:
        conn.close()


def increment_message_count(user):
    if not user or user.is_bot:
        return

    conn = _connect()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.bot_users
                        (user_id, first_name, username, message_count)
                    VALUES (%s, %s, %s, 1)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        username = EXCLUDED.username,
                        message_count =
                            public.bot_users.message_count + 1,
                        updated_at = NOW()
                    """,
                    (
                        user.id,
                        user.first_name or "",
                        user.username,
                    ),
                )
    finally:
        conn.close()


def get_user(user_id):
    conn = _connect()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, first_name, username, message_count
                FROM public.bot_users
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def find_user_by_username(username):
    username = username.lstrip("@").strip()

    if not username:
        return None

    conn = _connect()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, first_name, username, message_count
                FROM public.bot_users
                WHERE LOWER(username) = LOWER(%s)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()
