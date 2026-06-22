from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(is_participant: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if not is_participant:
        buttons.append([InlineKeyboardButton(text="🎟 شرکت در قرعه‌کشی", callback_data="join_lottery")])
    else:
        buttons += [
            [InlineKeyboardButton(text="👥 دعوت دوستان", callback_data="invite"),
             InlineKeyboardButton(text="📊 آمار من", callback_data="my_stats")],
            [InlineKeyboardButton(text="🏆 رتبه‌بندی", callback_data="leaderboard"),
             InlineKeyboardButton(text="💰 استخر جایزه", callback_data="prize_pool")],
            [InlineKeyboardButton(text="🍀 شانس من", callback_data="my_chance"),
             InlineKeyboardButton(text="📋 وضعیت دعوت‌ها", callback_data="referral_status")],
            [InlineKeyboardButton(text="ℹ️ اطلاعات مسابقه", callback_data="contest_info")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def join_channels_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch_id, title in channels:
        name = title or ch_id
        ch_str = str(ch_id)
        if ch_str.lstrip('-').isdigit():
            # کانال خصوصی: -1001234567890 → t.me/c/1234567890
            numeric = ch_str.lstrip('-')
            if numeric.startswith('100'):
                numeric = numeric[3:]
            link = f"https://t.me/c/{numeric}"
        else:
            link = f"https://t.me/{ch_str.lstrip('@')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {name}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ عضو شدم، بررسی کن", callback_data="check_membership")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def leaderboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 بر اساس تیکت", callback_data="lb_tickets"),
         InlineKeyboardButton(text="👥 بر اساس رفرال", callback_data="lb_referrals")],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data="back_main")]
    ])


def back_button(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت", callback_data=callback)]
    ])


def admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 آمار کلی", callback_data="admin_stats"),
         InlineKeyboardButton(text="📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎟 تیکت عضویت", callback_data="admin_set_join_tickets"),
         InlineKeyboardButton(text="👥 تیکت رفرال", callback_data="admin_set_ref_tickets")],
        [InlineKeyboardButton(text="💰 استخر اولیه", callback_data="admin_set_base_prize"),
         InlineKeyboardButton(text="📈 افزایش هر پله", callback_data="admin_set_prize_increment")],
        [InlineKeyboardButton(text="🏆 تعداد برنده‌ها", callback_data="admin_set_winners"),
         InlineKeyboardButton(text="➕ افزودن کانال", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="➖ حذف کانال", callback_data="admin_remove_channel"),
         InlineKeyboardButton(text="📋 لیست کانال‌ها", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="🎲 قرعه‌کشی آزمایشی", callback_data="admin_dry_lottery"),
         InlineKeyboardButton(text="🎉 اجرای قرعه‌کشی", callback_data="admin_run_lottery")],
        [InlineKeyboardButton(text="📜 گزارش قرعه‌ها", callback_data="admin_reports"),
         InlineKeyboardButton(text="📦 بکاپ", callback_data="admin_backup")],
        [InlineKeyboardButton(text="📤 خروجی اکسل", callback_data="admin_excel"),
         InlineKeyboardButton(text="🚫 لیست سیاه", callback_data="admin_blacklist")],
        [InlineKeyboardButton(text="🔄 شروع مسابقه جدید", callback_data="admin_new_competition")],
    ])


def broadcast_target_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 همه کاربران", callback_data="broadcast_all"),
         InlineKeyboardButton(text="🎟 فقط شرکت‌کنندگان", callback_data="broadcast_participants")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="admin_panel_back")]
    ])


def confirm_keyboard(yes_callback: str, no_callback: str = "admin_panel_back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله", callback_data=yes_callback),
         InlineKeyboardButton(text="❌ خیر", callback_data=no_callback)]
    ])


def admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 پنل مدیریت", callback_data="admin_panel_back")]
    ])
