import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        raise RuntimeError(
            "يجب إضافة DATABASE_URL في متغيرات بيئة الاستضافة"
        )

    return url


@contextmanager
def get_connection():
    """فتح اتصال وإغلاقه بأمان بعد انتهاء العملية."""
    conn = psycopg2.connect(
        _database_url(),
        connect_timeout=10,
        sslmode=os.getenv("DB_SSLMODE", "require"),
        cursor_factory=RealDictCursor,
    )

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ping_database() -> bool:
    """التأكد من أن قاعدة البيانات تستجيب."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            return cur.fetchone()["ok"] == 1


def save_user(
    user_id: int,
    first_name: str,
    username: str | None,
) -> None:
    """حفظ بيانات المستخدم وتحديثها عند عودته."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    user_id, first_name, username, updated_at
                )
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    username = EXCLUDED.username,
                    updated_at = NOW()
                """,
                (user_id, first_name or "", username),
            )


def save_chat(
    chat_id: int,
    title: str,
    owner_id: int | None = None,
) -> None:
    """حفظ المجموعة دون استبدال مالكها بمعرّف فارغ."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_chats (
                    chat_id, title, owner_id, updated_at
                )
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (chat_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    owner_id = COALESCE(
                        EXCLUDED.owner_id,
                        bot_chats.owner_id
                    ),
                    updated_at = NOW()
                """,
                (chat_id, title or "", owner_id),
            )


def set_group_owner(
    chat_id: int,
    owner_id: int,
    first_name: str,
    username: str | None,
) -> None:
    """تسجيل مالك المجموعة الحقيقي الذي تعيده Telegram."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    user_id, first_name, username, updated_at
                )
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    username = EXCLUDED.username,
                    updated_at = NOW()
                """,
                (owner_id, first_name or "", username),
            )

            cur.execute(
                """
                INSERT INTO bot_chats (
                    chat_id, title, owner_id, updated_at
                )
                VALUES (%s, '', %s, NOW())
                ON CONFLICT (chat_id) DO UPDATE SET
                    owner_id = EXCLUDED.owner_id,
                    updated_at = NOW()
                """,
                (chat_id, owner_id),
            )

            cur.execute(
                """
                INSERT INTO group_user_ranks (
                    chat_id, user_id, rank
                )
                VALUES (%s, %s, 'مالك')
                ON CONFLICT (chat_id, user_id, rank) DO NOTHING
                """,
                (chat_id, owner_id),
            )


def increment_message_count(
    chat_id: int,
    user_id: int,
) -> None:
    """زيادة عدد رسائل المستخدم في المجموعة بعملية واحدة."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO group_user_stats (
                    chat_id, user_id, message_count
                )
                VALUES (%s, %s, 1)
                ON CONFLICT (chat_id, user_id) DO UPDATE SET
                    message_count =
                        group_user_stats.message_count + 1
                """,
                (chat_id, user_id),
            )



def ensure_nawaf_developer(user_id: int) -> None:
    """تثبيت المطور الأعلى باستخدام آيدي تيليجرام الموثوق."""
    if user_id <= 0:
        raise ValueError("NAWAF_USER_ID must be a positive Telegram user ID")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # جدول المطورين مرتبط بجدول المستخدمين، لذلك نضمن وجوده أولًا.
            cur.execute(
                """
                INSERT INTO users (user_id, first_name, updated_at)
                VALUES (%s, 'Nawaf', NOW())
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )

            # المستوى 3 هو أعلى مستوى للمطورين.
            cur.execute(
                """
                INSERT INTO global_developers (
                    user_id, developer_level
                )
                VALUES (%s, 3)
                ON CONFLICT (user_id) DO UPDATE SET
                    developer_level = 3
                """,
                (user_id,),
            )

