# راهنمای نصب ربات قرعه‌کشی موشک صورتی 🚀🩷

## پیش‌نیازها
- Ubuntu 22.04 یا 24.04
- Python 3.10+

---

## ۱. آپلود فایل‌ها روی سرور

```bash
scp -r pink_rocket_bot/ user@your-server:/opt/pink_rocket_bot
```

---

## ۲. نصب Python و venv

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

cd /opt/pink_rocket_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## ۳. تنظیم .env

```bash
cp .env.example .env
nano .env
```

مقادیر زیر را پر کنید:
```
BOT_TOKEN=توکن_ربات_از_BotFather
ADMIN_IDS=آیدی_عددی_ادمین
DB_PATH=bot.db
```

---

## ۴. تست اجرا

```bash
source venv/bin/activate
python main.py
```

اگه پیام `Bot started` دیدی، همه چیز درسته. با Ctrl+C خارج شو.

---

## ۵. راه‌اندازی با systemd

```bash
sudo cp pink_rocket_bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/pink_rocket_bot.service
# User= را به نام کاربر سرورت تغییر بده

sudo systemctl daemon-reload
sudo systemctl enable pink_rocket_bot
sudo systemctl start pink_rocket_bot
```

بررسی وضعیت:
```bash
sudo systemctl status pink_rocket_bot
```

لاگ‌ها:
```bash
journalctl -u pink_rocket_bot -f
```

---

## ۶. دستورات مدیریت

در تلگرام:
- `/panel` — باز کردن پنل مدیریت (فقط ادمین)
- `/start` — شروع برای کاربران

---

## نکات مهم

- ربات باید **ادمین** تمام کانال‌ها باشد
- کانال‌ها را از پنل مدیریت (`➕ افزودن کانال`) اضافه کن
- قبل از قرعه‌کشی اصلی، حتماً قرعه‌کشی آزمایشی بزن
