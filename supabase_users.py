
import os
import logging

import psycopg2

log = logging.getLogger("Bot222.supabase_users")


def get_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise RuntimeError("متغير DATABASE_URL غير موجود.")

    return psycopg2.connect(
        database_url,
        sslmode="require",
        connect_timeout=10,
    )


def upsert_user(user_id, first_name="", username=None):
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
                    (user_id, first_name or "", username),
                )
    finally:
        conn.close()


def increment_message_count(user_id):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.bot_users
                    SET message_count = message_count + 1,
                        updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
    finally:
        conn.close()


def record_message(user_id, first_name="", username=None):
    """تسجيل المستخدم وزيادة عداد رسائله في عملية قاعدة بيانات واحدة."""
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
                    (user_id, first_name or "", username),
                )
    finally:
        conn.close()
