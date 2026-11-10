"""
Telegram Session String Generator
Run this script ONCE on your computer to log in and get your TELEGRAM_SESSION_STRING.
This string is what allows Render to connect without ever asking for an SMS/OTP in production.
"""

import sys

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("\n❌ Telethon is not installed.")
    print("Run: pip install telethon\n")
    sys.exit(1)

def main():
    print("=" * 60)
    print("  TELEGRAM SESSION STRING GENERATOR FOR RENDER")
    print("=" * 60)
    print("Get your API ID and API HASH from: https://my.telegram.org (under 'API development tools')\n")

    api_id_str = input("Enter API ID: ").strip()
    api_hash = input("Enter API HASH: ").strip()

    if not api_id_str.isdigit():
        print("❌ Error: API ID must be a number!")
        return

    api_id = int(api_id_str)

    print("\nConnecting to Telegram... (You will be prompted for your phone number and Telegram login code)")
    
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_str = client.session.save()
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! HERE IS YOUR TELEGRAM_SESSION_STRING:")
        print("=" * 60)
        print(session_str)
        print("=" * 60)
        print("\nKeep this string safe! Save it in your Render Environment Variables.")

        # Also write it locally to .env.local for convenience
        with open(".session_string.txt", "w", encoding="utf-8") as f:
            f.write(session_str)
        print("Saved a copy to .session_string.txt (do not commit this file to git!).\n")

if __name__ == "__main__":
    main()
