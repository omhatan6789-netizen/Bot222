
import html
import logging
import os
import re

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

import database
import supabase_users

log = logging.getLogger(__name__)

RANKS = {
    "nawaf": {
        "label": "🎖️Nawaf",
        "level": 0,
        "aliases": {"نواف", "nawaf"},
    },
    "dev": {
        "label": "Dev🎖️",
        "level": 1,
        "aliases": {"dev"},
    },
    "dev2": {
        "label": "Dev²🎖️",
        "level": 2,
        "aliases": {"dev2", "dev²", "dev 2"},
    },
    "owner": {
        "label": "المالك",
        "level": 3,
        "aliases": {"مالك", "المالك"},
    },
    "creator": {
        "label": "المنشئ",
        "level": 4,
        "aliases": {"منشئ", "المنشئ"},
    },
    "manager": {
        "label": "المدير",
        "level": 5,
        "aliases": {"مدير", "المدير"},
    },
    "admin": {
        "label": "الادمن",
        "level": 6,
        "aliases": {"ادمن", "أدمن", "الادمن", "الأدمن"},
    },
    "premium": {
        "label": "المميز",
        "level": 7,
        "aliases": {"مميز", "المميز"},
    },
    "member": {
        "label": "العضو",
        "level": 8,
        "aliases": {"عضو", "العضو"},
    },
}

COMMANDS = {
    "تنزيل الكل": "demote_all",
    "كشف المجموعة": "group_inspect",
    "رتبتي": "my_rank",
    "رتبته": "their_rank",
    "كشف": "inspect",
    "رفع": "promote",
    "تنزيل": "demote",
}

LISTS = {
    "المالكين": ("owner", "المالكين"),
    "المنشئين": ("creator", "المنشئين"),
    "المدراء": ("manager", "المدراء"),
    "الادمنية": ("admin", "الادمنية"),
    "الأدمنية": ("admin", "الادمنية"),
    "المميزين": ("premium", "المميزين"),
    "قائمة dev": ("dev", "Dev"),
    "قائمة dev2": ("dev2", "Dev2"),
    "قائمة dev 2": ("dev2", "Dev2"),
}

ID_RE = re.compile(r"^\d{5,20}$")


def owner_id():
    try:
        return int(os.getenv("OWNER_ID", "0"))
    except ValueError:
        return 0


def rank_keys(user_id, chat_id):
    keys = database.get_all_ranks(chat_id, user_id)

    if owner_id() and user_id == owner_id():
        keys.add("nawaf")

    return keys or {"member"}


def highest(keys):
    return min(
        keys,
        key=lambda key: RANKS.get(key, RANKS["member"])["level"],
    )


def label(key):
    return RANKS.get(key, RANKS["member"])["label"]


def mention(user_id, first_name, username=None):
    display = (
        "@" + username
        if username
        else (first_name or str(user_id))
    )
    return (
        f'<a href="tg://user?id={int(user_id)}">'
        f"{html.escape(display)}</a>"
    )


async def profile(user_id, chat_id):
    row = None

    try:
        row = supabase_users.get_user(user_id)
    except Exception:
        log.exception("Supabase profile lookup failed")

    first_name = (row or {}).get("first_name") or str(user_id)
    username = (row or {}).get("username")
    messages = (row or {}).get("message_count", 0)

    for item in database.get_group_members(chat_id):
        if item["user_id"] == user_id:
            first_name = item["first_name"] or first_name
            username = item["username"] or username
            break

    return first_name, username, messages


def parse(text):
    normalized = " ".join((text or "").strip().split())
    lower = normalized.lower()

    for command in sorted(COMMANDS, key=len, reverse=True):
        if lower == command or lower.startswith(command + " "):
            return (
                COMMANDS[command],
                normalized[len(command):].strip(),
                command,
            )

    if lower in LISTS:
        key, title = LISTS[lower]
        return "list", key, title

    return None


def rank_from(text):
    value = " ".join(text.lower().split())

    for key, info in RANKS.items():
        if value in info["aliases"]:
            return key

    return None


def permission_message(key):
    return (
        f"• اعذرني بس هذا الأمر لـ ↤︎〖 {label(key)} 〗وفوق فقط ."
    )


async def resolve_target(update, context):
    message = update.effective_message

    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        return {
            "id": user.id,
            "first_name": user.first_name,
            "username": user.username,
        }

    parts = (message.text or "").split()

    for token in parts[1:]:
        if ID_RE.fullmatch(token):
            user_id = int(token)

            try:
                row = supabase_users.get_user(user_id)
            except Exception:
                row = None

            return {
                "id": user_id,
                "first_name": (row or {}).get("first_name") or str(user_id),
                "username": (row or {}).get("username"),
            }

        if token.startswith("@"):
            try:
                row = supabase_users.find_user_by_username(token)
            except Exception:
                row = None

            if row:
                return {
                    "id": row["user_id"],
                    "first_name": row.get("first_name") or token,
                    "username": row.get("username"),
                }

            try:
                chat = await context.bot.get_chat(token)
                return {
                    "id": chat.id,
                    "first_name": getattr(chat, "first_name", None) or token,
                    "username": getattr(chat, "username", None) or token[1:],
                }
            except Exception:
                return None

    return None


def can_manage(actor_id, chat_id, target_id, key):
    if target_id == owner_id():
        return False, "protected"

    actor_level = RANKS[highest(rank_keys(actor_id, chat_id))]["level"]
    target_level = RANKS[highest(rank_keys(target_id, chat_id))]["level"]
    requested_level = RANKS[key]["level"]

    if actor_level >= requested_level:
        return False, "rank"

    if actor_level >= target_level:
        return False, "target"

    return True, ""


async def register_message(update):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or user.is_bot or not chat:
        return

    try:
        supabase_users.upsert_user(user)

        if message.text or message.caption:
            supabase_users.increment_message_count(user)
    except Exception:
        log.exception("Supabase user sync failed")

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        database.save_group_member(
            chat.id,
            user.id,
            user.first_name,
            user.username,
        )


async def command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user or user.is_bot:
        return

    await register_message(update)

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    parsed = parse(message.text or "")

    if not parsed:
        return

    action, rest, command = parsed

    if action == "my_rank":
        top = highest(rank_keys(user.id, chat.id))
        shown = html.escape(label(top))

        if user.id == owner_id():
            shown = f"<tg-spoiler>{shown}</tg-spoiler>"

        await message.reply_text(
            f"• رتبتك هي ↤︎ ‎{shown}",
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "group_inspect":
        await group_inspect(message, chat.id)
        return

    if action == "list":
        await rank_list(message, chat.id, rest, command)
        return

    target = await resolve_target(update, context)

    if not target:
        return

    target_id = target["id"]
    target_mention = mention(
        target_id,
        target.get("first_name"),
        target.get("username"),
    )

    if action in {"their_rank", "inspect"}:
        top = highest(rank_keys(target_id, chat.id))
        shown = html.escape(label(top))

        if target_id == owner_id():
            shown = f"<tg-spoiler>{shown}</tg-spoiler>"

        if action == "their_rank":
            await message.reply_text(
                f"• رتبته هي ↤︎ ‎{shown}",
                parse_mode=ParseMode.HTML,
            )
            return

        first_name, username, messages = await profile(
            target_id, chat.id
        )

        use = (
            html.escape("@" + username)
            if username
            else mention(target_id, first_name)
        )

        await message.reply_text(
            f"• ID : {target_id}\n"
            f"• USE : {use}\n"
            f"• STE : {shown}\n"
            f"• MSG : {messages}",
            parse_mode=ParseMode.HTML,
        )
        return

    if action in {"promote", "demote"}:
        key = rank_from(rest)

        if not key or key in {"member", "nawaf"}:
            return

        ok, reason = can_manage(
            user.id, chat.id, target_id, key
        )

        if not ok:
            if reason == "protected":
                await message.reply_text(
                    "• ما أقدر أغيّر رتب مطور البوت 🎖️."
                )
            elif reason == "rank":
                await message.reply_text(permission_message(key))
            else:
                await message.reply_text(
                    permission_message(
                        highest(rank_keys(target_id, chat.id))
                    )
                )
            return

        existing = rank_keys(target_id, chat.id)

        if action == "promote":
            if key in existing:
                await message.reply_text(
                    f"• المستخدم ↤︎ {target_mention}\n"
                    f"• عنده رتبة {label(key)} بالفعل.",
                    parse_mode=ParseMode.HTML,
                )
                return

            database.grant_rank(
                chat.id, target_id, key, user.id
            )

            shown = label(key)
            if key in {"owner", "creator", "manager", "admin", "premium"}:
                shown = shown[1:]

            await message.reply_text(
                f"• تمام رفعته {shown} .\n"
                f"• المستخدم ↤︎ {target_mention}",
                parse_mode=ParseMode.HTML,
            )
            return

        if key not in existing:
            await message.reply_text(
                f"• المستخدم ↤︎ {target_mention}\n"
                f"• ما عنده رتبة {label(key)}.",
                parse_mode=ParseMode.HTML,
            )
            return

        database.revoke_rank(chat.id, target_id, key)

        shown = label(key)
        if key in {"owner", "creator", "manager", "admin", "premium"}:
            shown = shown[1:]

        await message.reply_text(
            f"• تمام نزلته من {shown}\n"
            f"• المستخدم ↤︎ {target_mention}",
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "demote_all":
        actor_level = RANKS[highest(rank_keys(user.id, chat.id))]["level"]
        removable = []

        for key in rank_keys(target_id, chat.id):
            if key in {"nawaf", "member"}:
                continue

            if (
                actor_level < RANKS[key]["level"]
                and target_id != owner_id()
            ):
                removable.append(key)

        if not removable:
            await message.reply_text(
                "• اعذرني بس هذا الأمر ما يسمح لك بتنزيل رتب هذا المستخدم."
            )
            return

        database.revoke_all_ranks(chat.id, target_id, removable)

        names = "، ".join(
            label(key).removeprefix("ال")
            for key in sorted(
                removable,
                key=lambda item: RANKS[item]["level"],
            )
        )

        await message.reply_text(
            f"• تم تنزيل المستخدم ↤︎ {target_mention}\n"
            f"نزلته من ( {names} )",
            parse_mode=ParseMode.HTML,
        )


async def group_inspect(message, chat_id):
    sections = [
        ("owner", "المالكين"),
        ("creator", "المنشئين"),
        ("manager", "المدراء"),
        ("admin", "الادمنية"),
        ("premium", "المميزين"),
    ]

    lines = ["كشف المجموعة: 📋", ""]

    for key, title in sections:
        lines.extend([f"• قائمة {title}", "━━━━━━━━━━━━"])
        user_ids = database.list_group_rank_holders(chat_id, key)

        if not user_ids:
            lines.append("لا يوجد")
        else:
            for index, user_id in enumerate(user_ids, 1):
                first_name, username, _ = await profile(
                    user_id, chat_id
                )
                lines.append(
                    f"{index} - {mention(user_id, first_name, username)}"
                )

        lines.append("")

    await message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


async def rank_list(message, chat_id, key, title):
    user_ids = database.list_group_rank_holders(chat_id, key)
    lines = [f"• قائمة {title}", "━━━━━━━━━━━━"]

    if not user_ids:
        lines.append("لا يوجد")
    else:
        for index, user_id in enumerate(user_ids, 1):
            first_name, username, _ = await profile(user_id, chat_id)
            lines.append(
                f"{index} - {mention(user_id, first_name, username)}"
            )

    await message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


async def on_my_chat_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    change = update.my_chat_member

    if not change or change.new_chat_member.status not in {
        "member", "administrator"
    }:
        return

    chat = change.chat

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        creator = next(
            (item.user for item in admins if item.status == "creator"),
            None,
        )

        if creator:
            database.grant_rank(
                chat.id, creator.id, "owner", change.from_user.id
            )
            database.save_group_member(
                chat.id,
                creator.id,
                creator.first_name,
                creator.username,
            )

            try:
                supabase_users.upsert_user(creator)
            except Exception:
                log.exception("Creator Supabase sync failed")

    except Exception:
        log.exception(
            "Could not detect creator for chat %s", chat.id
        )


def register_handlers(app):
    app.add_handler(
        ChatMemberHandler(
            on_my_chat_member,
            ChatMemberHandler.MY_CHAT_MEMBER,
        ),
        group=0,
    )

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            command_handler,
        ),
        group=10,
    )
