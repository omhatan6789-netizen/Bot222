
import os
import logging

import psycopg2
from psycopg2.extras import RealDictCursor

log = logging.getLogger("Bot222.supabase_users")


def get_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("متغير DATABASE_URL غير موجود.")

    return psycopg2.connect(
        database_url,
        sslmode="require",
        connect_timeout=10,
        cursor_factory=RealDictCursor,
    )


def upsert_user(user, first_name=None, username=None):
    """يدعم كائن مستخدم تيليجرام أو تمرير بيانات المستخدم منفصلة."""
    if hasattr(user, "id"):
        user_id = user.id
        first_name = user.first_name or ""
        username = user.username
    else:
        user_id = int(user)
        first_name = first_name or ""

    conn = get_connection()
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
                    (user_id, first_name, username),
                )
    finally:
        conn.close()


def increment_message_count(user, first_name=None, username=None):
    if hasattr(user, "id"):
        user_id = user.id
        first_name = user.first_name or ""
        username = user.username
    else:
        user_id = int(user)
        first_name = first_name or ""

    conn = get_connection()
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
                    (user_id, first_name, username),
                )
    finally:
        conn.close()


def record_message(user, first_name=None, username=None):
    """تسجيل المستخدم وزيادة عدد رسائله في استعلام واحد."""
    increment_message_count(user, first_name, username)


def get_user(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, first_name, username, message_count
                FROM public.bot_users
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            return cur.fetchone()
    finally:
        conn.close()


def find_user_by_username(username):
    username = (username or "").strip().lstrip("@")
    if not username:
        return None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, first_name, username, message_count
                FROM public.bot_users
                WHERE LOWER(username) = LOWER(%s)
                LIMIT 1
                """,
                (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()
