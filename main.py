import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, DB_PATH
from database import init_db
import handler_user
import handler_admin
from scheduler import membership_check_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handler_admin.router)
    dp.include_router(handler_user.router)

    logging.info("Bot started.")

    # scheduler و polling رو همزمان اجرا کن
    await asyncio.gather(
        dp.start_polling(bot, skip_updates=True),
        membership_check_loop(bot, interval_hours=3),
    )


if __name__ == "__main__":
    asyncio.run(main())
