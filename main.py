
import logging
import os

from telegram.ext import Application

import database
import ranks


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

log = logging.getLogger("Bot222")


def main():
    token = os.getenv("BOT_TOKEN", "").strip()

    if not token:
        raise RuntimeError(
            "ضع توكن تيليجرام في متغير BOT_TOKEN في إعدادات الاستضافة."
        )

    database.init_db()

    app = Application.builder().token(token).build()

    ranks.register_handlers(app)

    log.info("Starting Bot222")

    app.run_polling(
        allowed_updates=["message", "my_chat_member"]
    )


if __name__ == "__main__":
    main()
