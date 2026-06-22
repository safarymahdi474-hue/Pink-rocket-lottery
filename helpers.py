import random
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
import database as db


async def check_user_joined_all(bot: Bot, user_id: int) -> tuple:
    channels = await db.get_channels()
    not_joined = []
    # FIX: unpack 3 values (channel_id, title, invite_link)
    for ch_id, title, invite_link in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ("left", "kicked", "banned"):
                not_joined.append((ch_id, title, invite_link))
        except Exception:
            not_joined.append((ch_id, title, invite_link))
    return len(not_joined) == 0, not_joined


async def calculate_prize_pool() -> float:
    base = float(await db.get_setting("base_prize"))
    increment = float(await db.get_setting("prize_increment"))
    per_level = int(await db.get_setting("participants_per_level"))
    count = await db.get_participants_count()
    levels = count // per_level
    return base + (levels * increment)


async def get_prize_progress() -> dict:
    per_level = int(await db.get_setting("participants_per_level"))
    count = await db.get_participants_count()
    current_level_progress = count % per_level
    remaining = per_level - current_level_progress
    return {
        "count": count,
        "progress": current_level_progress,
        "per_level": per_level,
        "remaining": remaining
    }


async def run_weighted_lottery(bot: Bot, winners_count: int, dry_run: bool = False) -> list:
    participants = await db.get_all_participants()
    if not participants:
        return []

    pool = []
    for user_id, tickets, _, _, _ in participants:
        pool.extend([user_id] * tickets)

    if not pool:
        return []

    winners = []
    pool_copy = pool.copy()
    seen = set()

    for _ in range(min(winners_count, len(participants))):
        if not pool_copy:
            break
        available = [x for x in pool_copy if x not in seen]
        if not available:
            break
        winner_id = random.choice(available)
        seen.add(winner_id)
        pool_copy = [x for x in pool_copy if x != winner_id]

        for uid, tickets, referrals, username, full_name in participants:
            if uid == winner_id:
                winners.append({
                    "user_id": uid,
                    "username": username,
                    "full_name": full_name,
                    "tickets": tickets
                })
                break

    return winners


async def cleanup_invalid_participants(bot: Bot) -> int:
    ids = await db.get_all_participants_ids()
    removed = 0
    for user_id in ids:
        try:
            await bot.get_chat(user_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            await db.remove_participant(user_id)
            removed += 1
            continue

        channels = await db.get_channels()
        valid = True
        # FIX: unpack 3 values (channel_id, title, invite_link)
        for ch_id, title, invite_link in channels:
            try:
                member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
                if member.status in ("left", "kicked", "banned"):
                    valid = False
                    break
            except Exception:
                valid = False
                break

        if not valid:
            await db.remove_participant(user_id)
            removed += 1

    return removed


def format_number(n) -> str:
    return f"{int(float(n)):,}".replace(",", "،")
