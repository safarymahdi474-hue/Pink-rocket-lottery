import logging
import asyncio
from aiogram import Bot
import database as db
from helpers import check_user_joined_all

logger = logging.getLogger(__name__)


async def check_all_participants(bot: Bot):
    """هر چند ساعت یه بار همه شرکت‌کننده‌ها رو چک میکنه"""
    logger.info("Starting membership check for all participants...")
    ids = await db.get_all_participants_ids()
    suspended_count = 0
    restored_count = 0

    for user_id in ids:
        try:
            channels = await db.get_channels()
            if not channels:
                break

            all_joined, not_joined = await check_user_joined_all(bot, user_id)
            is_active = await db.is_active_participant(user_id)

            if not all_joined and is_active:
                # از کانالی خارج شده → suspend و پیام بده
                await db.suspend_participant(user_id)
                suspended_count += 1
                try:
                    await bot.send_message(
                        user_id,
                        "⚠️ شما از یکی از کانال‌های اجباری خارج شدید!\n\n"
                        "به همین دلیل موقتاً از قرعه‌کشی خارج شدید.\n\n"
                        "✅ تمام تیکت‌هایت حفظ شده — کافیه دوباره عضو کانال‌ها بشی.\n\n"
                        "برای بازگشت به قرعه‌کشی /start بزن.",
                        reply_markup=None
                    )
                except Exception:
                    pass  # کاربر ربات رو بلاک کرده

            elif all_joined and not is_active:
                # دوباره عضو شده → restore (بدون پیام، چون خودشون /start میزنن)
                await db.restore_participant(user_id)
                restored_count += 1

        except Exception as e:
            logger.error(f"Error checking user {user_id}: {e}")

        await asyncio.sleep(0.05)  # جلوگیری از flood

    logger.info(f"Membership check done. Suspended: {suspended_count}, Restored: {restored_count}")


async def membership_check_loop(bot: Bot, interval_hours: int = 3):
    """لوپ دوره‌ای — هر interval_hours ساعت یه بار اجرا میشه"""
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            await check_all_participants(bot)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
