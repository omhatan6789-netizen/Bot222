
"""نظام الرتب الأساسي لبوت نواف."""

import asyncio
import logging
import os
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import get_connection, save_user


logger = logging.getLogger(__name__)

# الرتب العامة أعلى من جميع رتب المجموعات.
GLOBAL_RANKS = {
    3: "Nawaf🎖️",
    2: "Dev🎖️",
    1: "Dev²🎖️",
}

# رتب المجموعة مرتبة من الأعلى إلى الأدنى.
GROUP_RANKS = {
    "مالك": 5,
    "منشئ": 4,
    "مدير": 3,
    "ادمن": 2,
    "مميز": 1,
}

RANK_ALIASES = {
    "ادمن": "ادمن",
    "أدمن": "ادمن",
    "ادمين": "ادمن",
    "مميز": "مميز",
    "مدير": "مدير",
    "منشئ": "منشئ",
    "مالك": "مالك",
}

RANK_ORDER = {
    **{name: level + 5 for level, name in GLOBAL_RANKS.items()},
    **GROUP_RANKS,
    "عضو": 0,
}

RANK_COMMAND = re.compile(
    r"^\s*(رفع|تنزيل)\s+(ادمن|أدمن|ادمين|مميز|مدير|منشئ|مالك|الكل)"
    r"(?:\s+(.+))?\s*$",
    re.IGNORECASE,
)


def _global_rank(user_id: int) -> tuple[int, str]:
    """إرجاع الرتبة العامة المحفوظة في قاعدة البيانات."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT developer_level
                FROM global_developers
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        return 0, "عضو"

    level = int(row["developer_level"])
    return level + 5, GLOBAL_RANKS.get(level, "عضو")


def _group_ranks(chat_id: int, user_id: int) -> list[str]:
    """إرجاع جميع رتب المستخدم في المجموعة."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rank
                FROM group_user_ranks
                WHERE chat_id = %s AND user_id = %s
                """,
                (chat_id, user_id),
            )
            rows = cur.fetchall()

    return [
        row["rank"]
        for row in rows
        if row["rank"] in GROUP_RANKS
    ]


def _highest_rank(chat_id: int, user_id: int) -> tuple[int, str]:
    """تحديد أعلى رتبة عامة أو رتبة مجموعة."""
    global_level, global_name = _global_rank(user_id)

    if global_level:
        return global_level, global_name

    ranks = _group_ranks(chat_id, user_id)

    if not ranks:
        return 0, "عضو"

    rank = max(ranks, key=lambda name: GROUP_RANKS[name])
    return GROUP_RANKS[rank], rank


def _resolve_user_id_sync(
    chat_id: int,
    username: str,
) -> int | None:
    """البحث عن مستخدم سبق للبوت أن حفظ بياناته."""
    clean_username = username.lstrip("@").strip()

    if not clean_username:
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE LOWER(username) = LOWER(%s)
                LIMIT 1
                """,
                (clean_username,),
            )
            row = cur.fetchone()

    return int(row["user_id"]) if row else None


def _change_rank_sync(
    chat_id: int,
    target_id: int,
    rank: str,
    action: str,
) -> bool:
    """إضافة رتبة أو حذفها دون حذف الرتب الأخرى."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if action == "رفع":
                cur.execute(
                    """
                    INSERT INTO group_user_ranks (
                        chat_id, user_id, rank
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chat_id, user_id, rank)
                    DO NOTHING
                    """,
                    (chat_id, target_id, rank),
                )
            else:
                cur.execute(
                    """
                    DELETE FROM group_user_ranks
                    WHERE chat_id = %s
                      AND user_id = %s
                      AND rank = %s
                    """,
                    (chat_id, target_id, rank),
                )
                return cur.rowcount > 0

    return True


def _mention(user_id: int, name: str) -> str:
    safe_name = (
        name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


async def rank_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """معالجة أوامر الرتب العربية بدون شرطة مائلة."""
    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if (
        not message
        or not chat
        or not actor
        or chat.type not in ("group", "supergroup")
        or not message.text
    ):
        return

    text = message.text.strip()

    # عرض رتبة المستخدم الذي أرسل الأمر.
    if text == "رتبتي":
        try:
            _, rank = await asyncio.to_thread(
                _highest_rank, chat.id, actor.id
            )
            await message.reply_text(
                f"• رتبتك هي ↤︎ ‎{rank}"
            )
        except Exception:
            logger.exception("Failed to read own rank")
            await message.reply_text("تعذر جلب رتبتك حاليًا.")
        return

    # عرض رتبة المستخدم الذي تم الرد على رسالته.
    if text == "رتبته":
        if not message.reply_to_message:
            await message.reply_text(
                "• رد على رسالة الشخص اللي تبي تعرف رتبته."
            )
            return

        target = message.reply_to_message.from_user

        if not target:
            return

        try:
            _, rank = await asyncio.to_thread(
                _highest_rank, chat.id, target.id
            )
            shown_rank = (
                f"<tg-spoiler>{rank}</tg-spoiler>"
                if rank == "Nawaf🎖️"
                else rank
            )
            await message.reply_text(
                f"• رتبته هي ↤︎ ‎{shown_rank}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logger.exception("Failed to read target rank")
            await message.reply_text("تعذر جلب الرتبة حاليًا.")
        return

    match = RANK_COMMAND.fullmatch(text)

    if not match:
        return

    action, requested_rank, target_text = match.groups()
    requested_rank = RANK_ALIASES.get(
        requested_rank.lower(), requested_rank
    )

    if requested_rank == "الكل" and action == "رفع":
        return

    # تحديد الشخص المستهدف: الرد أولًا، ثم ID أو username.
    target = None

    if message.reply_to_message:
        target = message.reply_to_message.from_user

    elif target_text:
        target_text = target_text.strip()

        if target_text.isdigit() or (
            target_text.startswith("-")
            and target_text[1:].isdigit()
        ):
            class Target:
                id = int(target_text)
                first_name = target_text
                username = None

            target = Target()

        elif target_text.startswith("@"):
            try:
                target_id = await asyncio.to_thread(
                    _resolve_user_id_sync,
                    chat.id,
                    target_text,
                )
                if target_id is not None:
                    class Target:
                        id = target_id
                        first_name = target_text
                        username = target_text.lstrip("@")

                    target = Target()
            except Exception:
                logger.exception("Failed to find username")

    if target is None:
        await message.reply_text(
            "• رد على رسالة المستخدم أو اكتب آيدي أو يوزر معروف للبوت."
        )
        return

    try:
        actor_level, _ = await asyncio.to_thread(
            _highest_rank, chat.id, actor.id
        )
        target_level, target_rank = await asyncio.to_thread(
            _highest_rank, chat.id, target.id
        )

        if action == "رفع":
            required_level = GROUP_RANKS[requested_rank]

            # لا يستطيع منح رتبة مساوية أو أعلى من رتبته.
            if actor_level <= required_level:
                await message.reply_text(
                    "• اعذرني بس هذا الأمر لـ "
                    f"↤︎〖 {requested_rank} 〗وفوق فقط ."
                )
                return

            if target.id != actor.id and target_level >= actor_level:
                await message.reply_text(
                    "• صحصح شف من الي تبي ترفع رتبته ياورع!"
                )
                return

            await asyncio.to_thread(
                _change_rank_sync,
                chat.id,
                target.id,
                requested_rank,
                "رفع",
            )

            await message.reply_text(
                "• تمام رفعته "
                f"{requested_rank} .\n"
                f"• المستخدم ↤︎ {_mention(target.id, target.first_name)}",
                parse_mode=ParseMode.HTML,
            )
            return

        # تنزيل رتبة محددة، أو كل الرتب الأدنى التي يحق للمنفذ حذفها.
        if requested_rank == "الكل":
            existing = await asyncio.to_thread(
                _group_ranks, chat.id, target.id
            )
            removable = [
                rank for rank in existing
                if GROUP_RANKS[rank] < actor_level
            ]

            if not removable:
                await message.reply_text(
                    "• ما عنده رتب تقدر تنزلها."
                )
                return

            for rank in removable:
                await asyncio.to_thread(
                    _change_rank_sync,
                    chat.id,
                    target.id,
                    rank,
                    "تنزيل",
                )

            names = "، ".join(removable)
            await message.reply_text(
                "• تم تنزيل المستخدم︎ ↤︎ "
                f"{_mention(target.id, target.first_name)}\n"
                f"نزلته من ( {names} )",
                parse_mode=ParseMode.HTML,
            )
            return

        if GROUP_RANKS[requested_rank] >= actor_level:
            await message.reply_text(
                "• اعذرني بس هذا الأمر لـ "
                f"↤︎〖 {requested_rank} 〗وفوق فقط ."
            )
            return

        existing = await asyncio.to_thread(
            _group_ranks, chat.id, target.id
        )

        if requested_rank not in existing:
            await message.reply_text(
                "• المستخدم ما عنده هذي الرتبة."
            )
            return

        await asyncio.to_thread(
            _change_rank_sync,
            chat.id,
            target.id,
            requested_rank,
            "تنزيل",
        )

        await message.reply_text(
            f"• تمام نزلته من {requested_rank}\n"
            f"• المستخدم ↤︎ {_mention(target.id, target.first_name)}",
            parse_mode=ParseMode.HTML,
        )

    except Exception:
        logger.exception("Rank command failed")
        await message.reply_text(
            "صار خطأ أثناء تنفيذ الأمر. تأكد من اتصال قاعدة البيانات."
        )


def register_rank_handlers(app: Application) -> None:
    """تسجيل معالج أوامر الرتب العربية."""
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            rank_message,
        ),
        group=1,
    )
