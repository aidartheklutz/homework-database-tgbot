# Homework Database Telegram Bot

Readme: **English** | [Русский](/README.rus.md)

Telegram bot for a study group. An administrator publishes homework, and students quickly find today’s, tomorrow’s, active, and past assignments. Data lives in SQLite; finished homework stays in the database and remains available through history.

## Features

**Student commands**

- `/today` – homework due today
- `/tmrw` – homework due tomorrow
- `/active` – choose a month with active homework
- `/active all` – all currently active homework
- `/history` – choose a month with past homework
- `/history 2026-04-11` – all past homework with that deadline
- `/history 2026-04-11 Math, Physics` – past homework only for the listed subjects

**Admin commands**

- `/share` – publish new homework (step-by-step: subject → description → optional photo → start date → deadline)
- `/edit` – edit existing homework (subject, description, photo, dates)
- `/delete` – delete homework
- `/cancel` – cancel the current multi-step operation

Example student query:

```
/history 2026-04-11 Math, Physics

Math
From: 01.04.2026
Until: 11.04.2026

Solve problems 1–15.
```

After `/share` the bot asks for subject, description (text or photo with caption), optional photo, start date, and deadline. Dates can be entered as `2026-11-03` or with time as `2026-11-07 23:59`. If time is omitted for the deadline, it defaults to 23:59.

## Tech Stack

- **Python**
- **pyTelegramBotAPI** (TeleBot)
- **SQLite** (single table `homework`)
- **python-dotenv**
- **tzdata** / `zoneinfo` (timezone support, default `Asia/Bishkek`)
- **pytest**

Project layout:

```
bot/
├── config.py
├── main.py
├── database/ # Database + repository
├── handlers/ # Student + admin command handlers
├── services/ # Business logic
└── utils/ # Dates, formatting, development helpers
```

## Getting Started

1. Clone the repository:

   ```
   git clone https://github.com/aidartheklutz/homework-database-tgbot.git
   cd homework-database-tgbot
   ```

2. Create and activate a virtual environment:

   ```
   python -m venv .venv
   source .venv/bin/activate # Linux/macOS

   # or .venv\Scripts\activate on Windows

   ```

3. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

4. Copy the example environment file and fill in the values:

   ```
   cp .env.example .env
   ```

   ```
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_IDS=123456789,987654321
   DATABASE_PATH=homework.db
   TIMEZONE=Asia/Bishkek
   ```

5. Run the bot:
   ```
   python main.py
   ```

`homework.db` is created automatically next to the entry point. The schema contains one table `homework`; status (active / past) is computed from `start_at` and `deadline` in the configured timezone. Do not commit `.env` – it is already listed in `.gitignore`.

## Deployment

On a server set the same environment variables, ensure persistent storage for the SQLite file, and keep the process running with systemd, Docker, or another process manager. The MVP uses long polling, so only one bot instance should run against a single database.

## Tests

```
pytest
```

## Clearing test data

For development there is a helper that wipes all homework records from the database configured in `.env` (it is **not** a Telegram command):

```
python -c "from bot.utils.development import clear_current_database; print(clear_current_database())"
```

## License

This project is provided as-is for educational / study-group use.
