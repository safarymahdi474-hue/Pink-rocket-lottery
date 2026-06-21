import aiosqlite
import json
from datetime import datetime
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL UNIQUE,
            title TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blacklisted INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS participants (
            user_id INTEGER PRIMARY KEY,
            tickets INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referrer_id INTEGER,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lottery_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            participants_count INTEGER,
            total_tickets INTEGER,
            prize_pool REAL,
            winners_count INTEGER,
            winners_data TEXT
        );

        INSERT OR IGNORE INTO settings VALUES ('join_tickets', '1');
        INSERT OR IGNORE INTO settings VALUES ('referral_tickets', '2');
        INSERT OR IGNORE INTO settings VALUES ('base_prize', '1000000');
        INSERT OR IGNORE INTO settings VALUES ('prize_increment', '500000');
        INSERT OR IGNORE INTO settings VALUES ('winners_count', '1');
        INSERT OR IGNORE INTO settings VALUES ('participants_per_level', '100');
        """)
        await db.commit()


async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
        await db.commit()


# ─── CHANNELS ───────────────────────────────────────────────

async def add_channel(channel_id: str, title: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO channels (channel_id, title) VALUES (?,?)",
            (channel_id, title)
        )
        await db.commit()


async def remove_channel(channel_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
        await db.commit()


async def get_channels() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT channel_id, title FROM channels") as cur:
            return await cur.fetchall()


# ─── USERS ───────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES (?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name
        """, (user_id, username, full_name))
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return {"user_id": row[0], "username": row[1], "full_name": row[2],
                        "joined_at": row[3], "is_blacklisted": row[4]}
            return None


async def is_blacklisted(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_blacklisted FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])


async def set_blacklist(user_id: int, status: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blacklisted=? WHERE user_id=?", (int(status), user_id))
        await db.commit()


async def get_all_user_ids() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_blacklisted=0") as cur:
            return [r[0] for r in await cur.fetchall()]


# ─── PARTICIPANTS ─────────────────────────────────────────────

async def is_participant(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM participants WHERE user_id=?", (user_id,)) as cur:
            return bool(await cur.fetchone())


async def add_participant(user_id: int, referrer_id: int = None):
    join_tickets = int(await get_setting("join_tickets"))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO participants (user_id, tickets, referral_count, referrer_id)
            VALUES (?,?,0,?)
        """, (user_id, join_tickets, referrer_id))
        await db.commit()


async def get_participant(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM participants WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return {"user_id": row[0], "tickets": row[1], "referral_count": row[2],
                        "referrer_id": row[3], "joined_at": row[4]}
            return None


async def add_tickets(user_id: int, count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE participants SET tickets=tickets+? WHERE user_id=?", (count, user_id))
        await db.commit()


async def get_all_participants() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.user_id, p.tickets, p.referral_count, u.username, u.full_name
            FROM participants p JOIN users u ON p.user_id=u.user_id
            WHERE u.is_blacklisted=0
        """) as cur:
            return await cur.fetchall()


async def get_participants_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM participants p JOIN users u ON p.user_id=u.user_id WHERE u.is_blacklisted=0") as cur:
            return (await cur.fetchone())[0]


async def get_total_tickets() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT SUM(tickets) FROM participants p JOIN users u ON p.user_id=u.user_id WHERE u.is_blacklisted=0") as cur:
            row = await cur.fetchone()
            return row[0] or 0


async def get_leaderboard(by: str = "tickets", limit: int = 10) -> list:
    col = "tickets" if by == "tickets" else "referral_count"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(f"""
            SELECT p.user_id, u.username, u.full_name, p.tickets, p.referral_count
            FROM participants p JOIN users u ON p.user_id=u.user_id
            WHERE u.is_blacklisted=0
            ORDER BY p.{col} DESC LIMIT ?
        """, (limit,)) as cur:
            return await cur.fetchall()


async def get_user_rank(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*)+1 FROM participants p JOIN users u ON p.user_id=u.user_id
            WHERE u.is_blacklisted=0 AND p.tickets > (SELECT tickets FROM participants WHERE user_id=?)
        """, (user_id,)) as cur:
            return (await cur.fetchone())[0]


# ─── REFERRALS ───────────────────────────────────────────────

async def has_referral(referred_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM referrals WHERE referred_id=?", (referred_id,)) as cur:
            return bool(await cur.fetchone())


async def add_referral(referrer_id: int, referred_id: int):
    ref_tickets = int(await get_setting("referral_tickets"))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id, status)
            VALUES (?,?,'confirmed')
        """, (referrer_id, referred_id))
        await db.execute("UPDATE participants SET referral_count=referral_count+1, tickets=tickets+? WHERE user_id=?",
                         (ref_tickets, referrer_id))
        await db.commit()


async def get_referral_list(referrer_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT r.referred_id, u.username, u.full_name, r.status
            FROM referrals r JOIN users u ON r.referred_id=u.user_id
            WHERE r.referrer_id=?
        """, (referrer_id,)) as cur:
            return await cur.fetchall()


# ─── LOTTERY REPORT ──────────────────────────────────────────

async def save_lottery_report(participants_count, total_tickets, prize_pool, winners_count, winners_data):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO lottery_reports (participants_count, total_tickets, prize_pool, winners_count, winners_data)
            VALUES (?,?,?,?,?)
        """, (participants_count, total_tickets, prize_pool, winners_count, json.dumps(winners_data, ensure_ascii=False)))
        await db.commit()


async def get_lottery_reports(limit: int = 5) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM lottery_reports ORDER BY date DESC LIMIT ?", (limit,)) as cur:
            return await cur.fetchall()


# ─── RESET ───────────────────────────────────────────────────

async def reset_competition():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            DELETE FROM participants;
            DELETE FROM referrals;
        """)
        await db.commit()


# ─── REMOVE INVALID PARTICIPANTS ─────────────────────────────

async def remove_participant(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM participants WHERE user_id=?", (user_id,))
        await db.commit()


async def get_all_participants_ids() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM participants") as cur:
            return [r[0] for r in await cur.fetchall()]
