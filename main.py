
import asyncio
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database
from ranks import register_rank_handlers


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("nawafbot")


async def post_init(app: Application) -> None:
    """تهيئة المطور الأعلى عند بدء تشغيل البوت."""
    raw_id = os.getenv("NAWAF_USER_ID", "").strip()

    if not raw_id:
        logger.warning(
            "NAWAF_USER_ID is missing; global developer is not configured."
        )
        return

    try:
        nawaf_id = int(raw_id)

        await asyncio.to_thread(
            database.ensure_nawaf_developer,
            nawaf_id,
        )

        logger.info("Global developer initialized.")

    except ValueError:
        logger.error("NAWAF_USER_ID must be a numeric Telegram user ID.")

    except Exception:
        logger.exception("Failed to initialize global developer.")


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user:
        try:
            await asyncio.to_thread(
                database.save_user,
                user.id,
                user.first_name,
                user.username,
            )
        except Exception:
            logger.exception("Failed to save user")

    if message:
        await message.reply_text(
            "أهلًا بك في بوت نواف 🎖️\n"
            "البوت يعمل، ونعمل على تجهيز أنظمته."
        )


async def health(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message

    try:
        connected = await asyncio.to_thread(
            database.ping_database
        )
    except Exception:
        logger.exception("Database health check failed")
        connected = False

    if message:
        if connected:
            await message.reply_text(
                "الاتصال بقاعدة البيانات سليم ✅"
            )
        else:
            await message.reply_text(
                "تعذر الاتصال بقاعدة البيانات ❌"
            )


async def register_group_owner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    chat = update.effective_chat

    if not chat or chat.type not in ("group", "supergroup"):
        return

    try:
        admins = await context.bot.get_chat_administrators(
            chat.id
        )

        creator = next(
            (
                member.user
                for member in admins
                if member.status == "creator"
            ),
            None,
        )

        if creator:
            await asyncio.to_thread(
                database.set_group_owner,
                chat.id,
                creator.id,
                creator.first_name,
                creator.username,
            )

            await asyncio.to_thread(
                database.save_chat,
                chat.id,
                chat.title or "",
                creator.id,
            )
        else:
            await asyncio.to_thread(
                database.save_chat,
                chat.id,
                chat.title or "",
                None,
            )

    except Exception:
        logger.exception(
            "Failed to register group owner for %s",
            chat.id,
        )


async def bot_membership_changed(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    change = update.my_chat_member

    if not change:
        return

    old_status = change.old_chat_member.status
    new_status = change.new_chat_member.status

    if (
        new_status in ("member", "administrator")
        and old_status in ("left", "kicked")
    ):
        await register_group_owner(update, context)


async def count_group_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user or user.is_bot:
        return

    if chat.type not in ("group", "supergroup"):
        return

    try:
        await asyncio.to_thread(
            database.save_user,
            user.id,
            user.first_name,
            user.username,
        )

        await asyncio.to_thread(
            database.increment_message_count,
            chat.id,
            user.id,
        )

    except Exception:
        logger.exception(
            "Failed to process message in chat %s",
            chat.id,
        )


async def on_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Unhandled bot error",
        exc_info=context.error,
    )


def main() -> None:
    token = os.getenv("BOT_TOKEN", "").strip()

    if not token:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing"
        )

    app: Application = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))

    app.add_handler(
        ChatMemberHandler(
            bot_membership_changed,
            ChatMemberHandler.MY_CHAT_MEMBER,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            count_group_message,
        ),
        group=0,
    )

    register_rank_handlers(app)

    app.add_error_handler(on_error)

    logger.info("Starting NawafBot")
    app.run_polling(allowed_updates=Update.ALL_TYPES)



if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()

