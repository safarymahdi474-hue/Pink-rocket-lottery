import io
import json
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_IDS
from keyboards import (admin_panel, broadcast_target_keyboard,
                       confirm_keyboard, admin_back, back_button)
from helpers import (run_weighted_lottery, cleanup_invalid_participants,
                     calculate_prize_pool, format_number)
from excel_export import export_users_excel

router = Router()


class AdminStates(StatesGroup):
    waiting_broadcast_msg = State()
    waiting_broadcast_target = State()
    waiting_join_tickets = State()
    waiting_ref_tickets = State()
    waiting_base_prize = State()
    waiting_prize_increment = State()
    waiting_winners_count = State()
    waiting_add_channel = State()
    waiting_remove_channel = State()
    waiting_blacklist_id = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("panel"))
async def cmd_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔧 پنل مدیریت", reply_markup=admin_panel())


@router.callback_query(F.data == "admin_panel_back")
async def cb_admin_panel_back(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.answer()
    await call.message.edit_text("🔧 پنل مدیریت", reply_markup=admin_panel())


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    count = await db.get_participants_count()
    total_tickets = await db.get_total_tickets()
    all_users = await db.get_all_user_ids()
    prize = await calculate_prize_pool()
    await call.message.edit_text(
        f"📊 آمار کلی\n\n"
        f"👤 کل کاربران ربات: {len(all_users)}\n"
        f"🎟 شرکت‌کنندگان مسابقه: {count}\n"
        f"🎫 کل تیکت‌ها: {total_tickets}\n"
        f"💰 استخر فعلی: {format_number(prize)} تومان",
        reply_markup=admin_back()
    )


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await state.set_state(AdminStates.waiting_broadcast_target)
    await call.message.edit_text("📢 ارسال به چه گروهی؟", reply_markup=broadcast_target_keyboard())


@router.callback_query(F.data.in_({"broadcast_all", "broadcast_participants"}))
async def cb_broadcast_target(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await state.update_data(broadcast_target=call.data)
    await state.set_state(AdminStates.waiting_broadcast_msg)
    await call.message.edit_text("✏️ پیام خود را ارسال کنید:", reply_markup=admin_back())


@router.message(AdminStates.waiting_broadcast_msg)
async def process_broadcast(message: Message, bot: Bot, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    target = data.get("broadcast_target", "broadcast_all")
    await state.clear()

    if target == "broadcast_participants":
        participants = await db.get_all_participants()
        user_ids = [p[0] for p in participants]
    else:
        user_ids = await db.get_all_user_ids()

    sent = 0
    failed = 0
    status_msg = await message.answer(f"⏳ در حال ارسال به {len(user_ids)} نفر...")
    for uid in user_ids:
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            failed += 1
    await status_msg.edit_text(
        f"✅ ارسال تمام شد\n\n✔️ موفق: {sent}\n❌ ناموفق: {failed}",
        reply_markup=admin_back()
    )


async def _ask_value(call, state, state_to_set, prompt):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await state.set_state(state_to_set)
    await call.message.edit_text(prompt, reply_markup=admin_back())


@router.callback_query(F.data == "admin_set_join_tickets")
async def cb_set_join_tickets(call: CallbackQuery, state: FSMContext):
    cur = await db.get_setting("join_tickets")
    await _ask_value(call, state, AdminStates.waiting_join_tickets,
                     f"🎟 تیکت عضویت فعلی: {cur}\n\nمقدار جدید را وارد کنید:")


@router.message(AdminStates.waiting_join_tickets)
async def process_join_tickets(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int(message.text.strip())
        await db.set_setting("join_tickets", str(val))
        await state.clear()
        await message.answer(f"✅ تیکت عضویت به {val} تغییر یافت.", reply_markup=admin_back())
    except ValueError:
        await message.answer("❌ عدد صحیح وارد کنید.")


@router.callback_query(F.data == "admin_set_ref_tickets")
async def cb_set_ref_tickets(call: CallbackQuery, state: FSMContext):
    cur = await db.get_setting("referral_tickets")
    await _ask_value(call, state, AdminStates.waiting_ref_tickets,
                     f"👥 تیکت رفرال فعلی: {cur}\n\nمقدار جدید را وارد کنید:")


@router.message(AdminStates.waiting_ref_tickets)
async def process_ref_tickets(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int(message.text.strip())
        await db.set_setting("referral_tickets", str(val))
        await state.clear()
        await message.answer(f"✅ تیکت رفرال به {val} تغییر یافت.", reply_markup=admin_back())
    except ValueError:
        await message.answer("❌ عدد صحیح وارد کنید.")


@router.callback_query(F.data == "admin_set_base_prize")
async def cb_set_base_prize(call: CallbackQuery, state: FSMContext):
    cur = await db.get_setting("base_prize")
    await _ask_value(call, state, AdminStates.waiting_base_prize,
                     f"💰 استخر اولیه فعلی: {format_number(cur)} تومان\n\nمقدار جدید را وارد کنید:")


@router.message(AdminStates.waiting_base_prize)
async def process_base_prize(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = float(message.text.strip().replace(",", "").replace("،", ""))
        await db.set_setting("base_prize", str(val))
        await state.clear()
        await message.answer(f"✅ استخر اولیه به {format_number(val)} تومان تغییر یافت.", reply_markup=admin_back())
    except ValueError:
        await message.answer("❌ عدد وارد کنید.")


@router.callback_query(F.data == "admin_set_prize_increment")
async def cb_set_prize_increment(call: CallbackQuery, state: FSMContext):
    cur = await db.get_setting("prize_increment")
    await _ask_value(call, state, AdminStates.waiting_prize_increment,
                     f"📈 افزایش هر پله فعلی: {format_number(cur)} تومان\n\nمقدار جدید را وارد کنید:")


@router.message(AdminStates.waiting_prize_increment)
async def process_prize_increment(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = float(message.text.strip().replace(",", "").replace("،", ""))
        await db.set_setting("prize_increment", str(val))
        await state.clear()
        await message.answer(f"✅ افزایش هر پله به {format_number(val)} تومان تغییر یافت.", reply_markup=admin_back())
    except ValueError:
        await message.answer("❌ عدد وارد کنید.")


@router.callback_query(F.data == "admin_set_winners")
async def cb_set_winners(call: CallbackQuery, state: FSMContext):
    cur = await db.get_setting("winners_count")
    await _ask_value(call, state, AdminStates.waiting_winners_count,
                     f"🏆 تعداد برنده‌های فعلی: {cur}\n\nتعداد جدید را وارد کنید:")


@router.message(AdminStates.waiting_winners_count)
async def process_winners_count(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int(message.text.strip())
        await db.set_setting("winners_count", str(val))
        await state.clear()
        await message.answer(f"✅ تعداد برنده‌ها به {val} تغییر یافت.", reply_markup=admin_back())
    except ValueError:
        await message.answer("❌ عدد صحیح وارد کنید.")


@router.callback_query(F.data == "admin_add_channel")
async def cb_add_channel(call: CallbackQuery, state: FSMContext):
    await _ask_value(call, state, AdminStates.waiting_add_channel,
                     "➕ آیدی عددی یا یوزرنیم کانال را وارد کنید:\n\nمثال: @mychannel یا -1001234567890")


@router.message(AdminStates.waiting_add_channel)
async def process_add_channel(message: Message, bot: Bot, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    ch = message.text.strip()
    try:
        chat = await bot.get_chat(ch)
        await db.add_channel(str(chat.id), chat.title)
        await state.clear()
        await message.answer(f"✅ کانال «{chat.title}» اضافه شد.\n\n⚠️ مطمئن شو ربات ادمین این کانال است.",
                             reply_markup=admin_back())
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")


@router.callback_query(F.data == "admin_remove_channel")
async def cb_remove_channel(call: CallbackQuery, state: FSMContext):
    channels = await db.get_channels()
    if not channels:
        await call.answer("هیچ کانالی ثبت نشده!", show_alert=True)
        return
    text = "کانال‌ها:\n\n"
    for ch_id, title in channels:
        text += f"• {title or ch_id}: {ch_id}\n"
    text += "\nآیدی عددی کانال را برای حذف وارد کنید:"
    await _ask_value(call, state, AdminStates.waiting_remove_channel, text)


@router.message(AdminStates.waiting_remove_channel)
async def process_remove_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.remove_channel(message.text.strip())
    await state.clear()
    await message.answer(f"✅ کانال حذف شد.", reply_markup=admin_back())


@router.callback_query(F.data == "admin_list_channels")
async def cb_list_channels(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    channels = await db.get_channels()
    if not channels:
        text = "📋 هیچ کانالی ثبت نشده."
    else:
        lines = ["📋 لیست کانال‌ها\n"]
        for ch_id, title in channels:
            lines.append(f"• {title or '-'}: {ch_id}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=admin_back())


@router.callback_query(F.data == "admin_dry_lottery")
async def cb_dry_lottery(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    await call.answer("در حال اجرای قرعه‌کشی آزمایشی...")
    winners_count = int(await db.get_setting("winners_count"))
    winners = await run_weighted_lottery(bot, winners_count, dry_run=True)
    if not winners:
        await call.message.edit_text("❌ شرکت‌کننده‌ای وجود ندارد.", reply_markup=admin_back())
        return
    lines = ["🎲 قرعه‌کشی آزمایشی (ذخیره نمی‌شود)\n"]
    for i, w in enumerate(winners, 1):
        name = f"@{w['username']}" if w['username'] else w['full_name']
        lines.append(f"{i}. {name} — {w['tickets']} تیکت")
    await call.message.edit_text("\n".join(lines), reply_markup=admin_back())


@router.callback_query(F.data == "admin_run_lottery")
async def cb_run_lottery(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await call.message.edit_text(
        "⚠️ قرعه‌کشی اصلی اجرا شود؟\n\nقبل از اجرا، کاربران نامعتبر حذف می‌شوند.",
        reply_markup=confirm_keyboard("confirm_run_lottery")
    )


@router.callback_query(F.data == "confirm_run_lottery")
async def cb_confirm_lottery(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    status = await call.message.edit_text("⏳ در حال پاکسازی شرکت‌کنندگان نامعتبر...")
    removed = await cleanup_invalid_participants(bot)
    await status.edit_text(f"🧹 {removed} نفر حذف شدند.\n⏳ در حال اجرای قرعه‌کشی...")

    winners_count = int(await db.get_setting("winners_count"))
    winners = await run_weighted_lottery(bot, winners_count)
    if not winners:
        await status.edit_text("❌ شرکت‌کننده معتبری وجود ندارد.", reply_markup=admin_back())
        return

    prize = await calculate_prize_pool()
    total_t = await db.get_total_tickets()
    count = await db.get_participants_count()
    await db.save_lottery_report(count, total_t, prize, len(winners), winners)

    lines = ["🎉 قرعه‌کشی اجرا شد!\n"]
    for i, w in enumerate(winners, 1):
        name = f"@{w['username']}" if w['username'] else w['full_name']
        lines.append(f"🏆 برنده {i}: {name}\n🎟 تیکت: {w['tickets']}\n🆔 {w['user_id']}")
    await status.edit_text("\n".join(lines), reply_markup=admin_back())

    for w in winners:
        try:
            await bot.send_message(
                w['user_id'],
                f"🎉🏆 تبریک! شما برنده قرعه‌کشی موشک صورتی شدید!\n\n"
                f"💰 استخر جایزه: {format_number(prize)} تومان\n\n"
                f"به زودی با شما تماس گرفته می‌شود."
            )
        except Exception:
            pass


@router.callback_query(F.data == "admin_reports")
async def cb_admin_reports(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    reports = await db.get_lottery_reports()
    if not reports:
        await call.message.edit_text("📜 هنوز قرعه‌کشی اجرا نشده.", reply_markup=admin_back())
        return
    lines = ["📜 گزارش قرعه‌ها\n"]
    for r in reports:
        rid, date, p_count, total_t, prize, w_count, w_data = r
        lines.append(
            f"━━━━━━━━━━\n📅 {str(date)[:16]}\n"
            f"👥 شرکت‌کنندگان: {p_count}\n"
            f"🎟 تیکت‌ها: {total_t}\n"
            f"💰 استخر: {format_number(prize)}\n"
            f"🏆 برنده‌ها: {w_count}"
        )
    await call.message.edit_text("\n".join(lines), reply_markup=admin_back())


@router.callback_query(F.data == "admin_backup")
async def cb_backup(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    await call.answer("در حال آماده‌سازی بکاپ...")
    from config import DB_PATH
    with open(DB_PATH, "rb") as f:
        data = f.read()
    await bot.send_document(
        call.from_user.id,
        BufferedInputFile(data, filename="bot_backup.db"),
        caption="📦 بکاپ دیتابیس"
    )
    await call.message.edit_text("✅ بکاپ ارسال شد.", reply_markup=admin_back())


@router.callback_query(F.data == "admin_excel")
async def cb_excel(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    await call.answer("در حال آماده‌سازی اکسل...")
    buf = await export_users_excel()
    await bot.send_document(
        call.from_user.id,
        BufferedInputFile(buf.read(), filename="participants.xlsx"),
        caption="📤 خروجی اکسل شرکت‌کنندگان"
    )
    await call.message.edit_text("✅ فایل اکسل ارسال شد.", reply_markup=admin_back())


@router.callback_query(F.data == "admin_blacklist")
async def cb_blacklist(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await state.set_state(AdminStates.waiting_blacklist_id)
    await call.message.edit_text(
        "🚫 آیدی عددی کاربر را وارد کنید:",
        reply_markup=admin_back()
    )


@router.message(AdminStates.waiting_blacklist_id)
async def process_blacklist(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
        user = await db.get_user(uid)
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            return
        new_status = not user["is_blacklisted"]
        await db.set_blacklist(uid, new_status)
        if new_status:
            await db.remove_participant(uid)
        action = "به لیست سیاه اضافه" if new_status else "از لیست سیاه حذف"
        await state.clear()
        await message.answer(f"✅ کاربر {uid} {action} شد.", reply_markup=admin_back())
    except ValueError:
        await message.answer("❌ آیدی عددی وارد کنید.")


@router.callback_query(F.data == "admin_new_competition")
async def cb_new_competition(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await call.message.edit_text(
        "⚠️ با شروع مسابقه جدید همه داده‌ها صفر می‌شوند. ادامه می‌دهید؟",
        reply_markup=confirm_keyboard("confirm_new_competition")
    )


@router.callback_query(F.data == "confirm_new_competition")
async def cb_confirm_new_competition(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer()
    await db.reset_competition()
    await call.message.edit_text("✅ مسابقه جدید شروع شد!", reply_markup=admin_back())
