from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import database as db
from keyboards import (main_menu, join_channels_keyboard,
                       leaderboard_keyboard, back_button)
from helpers import (check_user_joined_all, check_and_update_participant_status,
                     calculate_prize_pool, get_prize_progress, format_number)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.full_name)

    if await db.is_blacklisted(user.id):
        await message.answer("❌ شما از مسابقه محروم شده‌اید.")
        return

    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            ref = int(args[1])
            if ref != user.id:
                referrer_id = ref
        except ValueError:
            pass

    if referrer_id:
        await db.set_setting(f"pending_ref_{user.id}", str(referrer_id))

    # اگه قبلاً شرکت کرده، وضعیت عضویت کانال‌ها رو چک کن
    if await db.is_participant(user.id):
        status = await check_and_update_participant_status(bot, user.id)

        if status == "suspended":
            # از کانالی خارج شده
            _, not_joined = await check_user_joined_all(bot, user.id)
            await message.answer(
                "⚠️ شما از یکی از کانال‌ها خارج شدید و موقتاً از قرعه‌کشی خارج شدید.\n\n"
                "برای بازگشت به قرعه‌کشی و حفظ تمام تیکت‌هایت، دوباره عضو کانال‌های زیر بشو:",
                reply_markup=join_channels_keyboard(not_joined)
            )
            return

        if status == "restored":
            p = await db.get_participant(user.id)
            await message.answer(
                f"✅ عضویت تأیید شد! به قرعه‌کشی برگشتی.\n\n"
                f"🎟 تیکت‌های تو: {p['tickets']}",
                reply_markup=main_menu(True)
            )
            return

        await message.answer("منوی اصلی 👇", reply_markup=main_menu(True))
        return

    # کاربر جدید — اول کانال‌ها رو چک کن
    channels = await db.get_channels()
    if channels:
        all_joined, not_joined = await check_user_joined_all(bot, user.id)
        if not all_joined:
            await message.answer(
                "👋 خوش اومدی!\n\n"
                "برای شرکت در قرعه‌کشی موشک صورتی 🚀🩷 ابتدا باید عضو کانال‌های زیر بشی:",
                reply_markup=join_channels_keyboard(not_joined)
            )
            return

    await message.answer(
        "👋 خوش اومدی!\n\nبرای شرکت در قرعه‌کشی موشک صورتی 🚀🩷 دکمه زیر رو بزن:",
        reply_markup=main_menu(False)
    )


@router.callback_query(F.data == "join_lottery")
async def cb_join_lottery(call: CallbackQuery, bot: Bot):
    user = call.from_user
    await call.answer()

    if await db.is_blacklisted(user.id):
        await call.message.edit_text("❌ شما از مسابقه محروم شده‌اید.")
        return

    if await db.is_participant(user.id):
        await call.message.edit_text("✅ شما قبلاً در مسابقه ثبت‌نام کرده‌اید.", reply_markup=main_menu(True))
        return

    all_joined, not_joined = await check_user_joined_all(bot, user.id)
    if not all_joined:
        await call.message.edit_text(
            "📢 برای شرکت در قرعه‌کشی باید عضو تمام کانال‌های زیر باشی:",
            reply_markup=join_channels_keyboard(not_joined)
        )
        return

    ref_setting = await db.get_setting(f"pending_ref_{user.id}")
    referrer_id = int(ref_setting) if ref_setting and ref_setting != "0" else None

    await db.add_participant(user.id, referrer_id)

    if referrer_id and await db.is_participant(referrer_id):
        if not await db.has_referral(user.id):
            await db.add_referral(referrer_id, user.id)
            p = await db.get_participant(referrer_id)
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 یک دعوت معتبر برای شما ثبت شد.\n\n"
                    f"👥 تعداد دعوت‌ها: {p['referral_count']}\n"
                    f"🎟 تعداد تیکت‌ها: {p['tickets']}"
                )
            except Exception:
                pass
        await db.set_setting(f"pending_ref_{user.id}", "0")

    join_tickets = int(await db.get_setting("join_tickets"))
    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={user.id}"

    await call.message.edit_text(
        f"✅ با موفقیت در قرعه‌کشی ثبت‌نام شدی!\n\n"
        f"🎟 تیکت‌های اولیه: {join_tickets}\n\n"
        f"🔗 لینک دعوت اختصاصی تو:\n{invite_link}\n\n"
        f"با دعوت دوستانت تیکت بیشتری بگیر!",
        reply_markup=main_menu(True)
    )


@router.callback_query(F.data == "check_membership")
async def cb_check_membership(call: CallbackQuery, bot: Bot):
    await call.answer("در حال بررسی...")
    user_id = call.from_user.id

    all_joined, not_joined = await check_user_joined_all(bot, user_id)

    if not all_joined:
        await call.message.edit_text(
            "❌ هنوز عضو همه کانال‌ها نشدی:",
            reply_markup=join_channels_keyboard(not_joined)
        )
        return

    # اگه قبلاً شرکت کرده بود و suspended بود → restore کن
    if await db.is_participant(user_id):
        if not await db.is_active_participant(user_id):
            await db.restore_participant(user_id)
            p = await db.get_participant(user_id)
            await call.message.edit_text(
                f"✅ عضویت تأیید شد! به قرعه‌کشی برگشتی 🎉\n\n"
                f"🎟 تمام تیکت‌هایت بازگردانده شد: {p['tickets']} تیکت",
                reply_markup=main_menu(True)
            )
            return
        await call.message.edit_text("منوی اصلی 👇", reply_markup=main_menu(True))
        return

    # کاربر جدید → ثبت‌نام
    await cb_join_lottery(call, bot)


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery):
    await call.answer()
    is_p = await db.is_active_participant(call.from_user.id)
    await call.message.edit_text("منوی اصلی 👇", reply_markup=main_menu(is_p))


@router.callback_query(F.data == "my_stats")
async def cb_my_stats(call: CallbackQuery):
    await call.answer()
    p = await db.get_participant(call.from_user.id)
    if not p:
        await call.answer("ابتدا در مسابقه شرکت کن!", show_alert=True)
        return
    status_text = "✅ فعال" if p.get("is_active") else "⏸ معلق (عضو کانال‌ها نیستی)"
    await call.message.edit_text(
        f"📊 آمار من\n\n"
        f"🎟 تعداد تیکت: {p['tickets']}\n"
        f"👥 تعداد دعوت: {p['referral_count']}\n"
        f"📅 تاریخ ثبت‌نام: {str(p['joined_at'])[:10]}\n"
        f"وضعیت: {status_text}",
        reply_markup=back_button()
    )


@router.callback_query(F.data == "my_chance")
async def cb_my_chance(call: CallbackQuery):
    await call.answer()
    p = await db.get_participant(call.from_user.id)
    if not p:
        await call.answer("ابتدا در مسابقه شرکت کن!", show_alert=True)
        return
    if not p.get("is_active"):
        await call.message.edit_text(
            "⏸ شما موقتاً از قرعه‌کشی خارج شدید.\n\n"
            "برای بازگشت، /start بزن و دوباره عضو کانال‌ها بشو.",
            reply_markup=back_button()
        )
        return
    total = await db.get_total_tickets()
    rank = await db.get_user_rank(call.from_user.id)
    percent = (p['tickets'] / total * 100) if total else 0
    await call.message.edit_text(
        f"🍀 شانس من\n\n"
        f"🎟 تعداد تیکت: {p['tickets']}\n"
        f"🏆 رتبه: {rank}\n"
        f"📊 سهم از کل تیکت‌ها: {percent:.2f}%",
        reply_markup=back_button()
    )


@router.callback_query(F.data == "invite")
async def cb_invite(call: CallbackQuery, bot: Bot):
    await call.answer()
    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    ref_tickets = await db.get_setting("referral_tickets")
    await call.message.edit_text(
        f"👥 دعوت دوستان\n\n"
        f"🔗 لینک اختصاصی تو:\n{invite_link}\n\n"
        f"🎟 به ازای هر دعوت معتبر {ref_tickets} تیکت دریافت می‌کنی!",
        reply_markup=back_button()
    )


@router.callback_query(F.data == "referral_status")
async def cb_referral_status(call: CallbackQuery, bot: Bot):
    await call.answer()
    refs = await db.get_referral_list(call.from_user.id)
    if not refs:
        text = "📋 هنوز کسی رو دعوت نکردی!"
    else:
        lines = ["📋 وضعیت دعوت‌ها\n"]
        for ref_id, username, full_name, status in refs:
            name = f"@{username}" if username else full_name or str(ref_id)
            channels = await db.get_channels()
            is_member = True
            for ch_id, title, invite_link in channels:
                try:
                    member = await bot.get_chat_member(chat_id=ch_id, user_id=ref_id)
                    if member.status in ("left", "kicked", "banned"):
                        is_member = False
                        break
                except Exception:
                    is_member = False
                    break
            is_part = await db.is_active_participant(ref_id)
            icon = "✅" if (is_part and is_member) else ("⏳" if not is_part else "❌")
            lines.append(f"{icon} {name}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_button())


@router.callback_query(F.data == "leaderboard")
async def cb_leaderboard(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text("🏆 رتبه‌بندی\n\nنمایش بر اساس:", reply_markup=leaderboard_keyboard())


@router.callback_query(F.data.in_({"lb_tickets", "lb_referrals"}))
async def cb_leaderboard_show(call: CallbackQuery):
    await call.answer()
    by = "tickets" if call.data == "lb_tickets" else "referrals"
    label = "تیکت" if by == "tickets" else "رفرال"
    rows = await db.get_leaderboard(by=by)
    lines = [f"🏆 برترین‌ها بر اساس {label}\n"]
    for i, (uid, username, full_name, tickets, referrals) in enumerate(rows, 1):
        name = f"@{username}" if username else full_name or str(uid)
        val = tickets if by == "tickets" else referrals
        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
        lines.append(f"{medal} {name} — {val} {label}")
    await call.message.edit_text("\n".join(lines), reply_markup=leaderboard_keyboard())


@router.callback_query(F.data == "prize_pool")
async def cb_prize_pool(call: CallbackQuery):
    await call.answer()
    base = float(await db.get_setting("base_prize"))
    increment = float(await db.get_setting("prize_increment"))
    current = await calculate_prize_pool()
    count = await db.get_participants_count()
    progress = await get_prize_progress()
    await call.message.edit_text(
        f"💰 استخر جایزه\n\n"
        f"💵 استخر اولیه: {format_number(base)} تومان\n"
        f"📈 افزایش هر پله: {format_number(increment)} تومان\n"
        f"👥 تعداد شرکت‌کنندگان: {count} نفر\n"
        f"💰 مبلغ فعلی: {format_number(current)} تومان\n\n"
        f"📈 تا افزایش بعدی جایزه:\n"
        f"{progress['progress']} / {progress['per_level']} نفر\n"
        f"⏳ {progress['remaining']} نفر تا افزایش بعدی باقی مانده",
        reply_markup=back_button()
    )


@router.callback_query(F.data == "contest_info")
async def cb_contest_info(call: CallbackQuery):
    await call.answer()
    join_t = await db.get_setting("join_tickets")
    ref_t = await db.get_setting("referral_tickets")
    winners = await db.get_setting("winners_count")
    current_prize = await calculate_prize_pool()
    count = await db.get_participants_count()
    total_t = await db.get_total_tickets()
    await call.message.edit_text(
        f"ℹ️ اطلاعات مسابقه\n\n"
        f"🎟 تیکت عضویت: {join_t}\n"
        f"👥 تیکت هر رفرال: {ref_t}\n"
        f"🏆 تعداد برنده‌ها: {winners}\n"
        f"👥 شرکت‌کنندگان: {count} نفر\n"
        f"🎟 کل تیکت‌ها: {total_t}\n"
        f"💰 استخر فعلی: {format_number(current_prize)} تومان",
        reply_markup=back_button()
    )
