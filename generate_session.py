"""
Telegram Session String Generator
Your API ID and API HASH are already pre-filled below!
Run this script:
    python generate_session.py
It will ask for:
  1. Your phone number (with country code, e.g. +91...)
  2. The Telegram login code sent to your Telegram app
Then it will automatically save your TELEGRAM_SESSION_STRING.
"""

import sys
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = 32751734
API_HASH = "6107561583effd9e9d245e7a46e839a4"

def main():
    print("=" * 60)
    print("  TELEGRAM SESSION STRING GENERATOR")
    print("=" * 60)
    print("Connecting with your API ID: 32751734...")
    print("Please enter your phone number when prompted.\n")

    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_str = client.session.save()
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! HERE IS YOUR TELEGRAM_SESSION_STRING:")
        print("=" * 60)
        print(session_str)
        print("=" * 60)

        # Save to file
        with open(".session_string.txt", "w", encoding="utf-8") as f:
            f.write(session_str)
        print("\n✅ Automatically saved to .session_string.txt")

if __name__ == "__main__":
    main()
