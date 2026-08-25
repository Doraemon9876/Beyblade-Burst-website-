# Beyblade-Burst-website-
# Telegram bridge

This bridge maps Episode 1 to Telegram message 1122 and increments the message ID through Episode 231.

It streams media in chunks and does not intentionally save the complete videos to disk.

## Setup

Install Python 3.10+ and run:

    pip install -r requirements.txt

Set the environment variables in `.env.example`.

Generate a Telethon StringSession with:

    python make_session.py

Then start:

    uvicorn main:app --host 0.0.0.0 --port 8000

Do not publish API hashes, session strings, login codes, passwords, or other Telegram credentials.

Before exposing this service publicly, put HTTPS and authentication in front of it.
