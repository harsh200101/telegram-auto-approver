"""
Telegram Session String Generator (with GUI popup fallback)
This script will prompt for your phone and login code via terminal or Windows dialog box.
"""

import sys
import os

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("❌ Telethon is not installed. Run: pip install --user telethon")
    sys.exit(1)

API_ID = 32751734
API_HASH = "6107561583effd9e9d245e7a46e839a4"

def get_user_input(title, prompt_text):
    """
    Attempts to read from terminal input.
    If EOFError occurs (e.g. running in non-interactive environment),
    it pops up a native Windows input box.
    """
    # 1. First check command line arguments if provided
    if "phone" in title.lower() and len(sys.argv) > 1:
        return sys.argv[1].strip()

    # 2. Try standard terminal input
    try:
        if sys.stdin and sys.stdin.isatty():
            val = input(f"{prompt_text} ").strip()
            if val:
                return val
    except (EOFError, Exception):
        pass

    # 3. Fallback to Windows GUI popup dialog
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        res = simpledialog.askstring(title, prompt_text, parent=root)
        root.destroy()
        if res:
            return res.strip()
    except Exception as e:
        print(f"Could not open GUI prompt: {e}")

    # 4. Fallback to reading from temporary text file
    filename = "input_phone.txt" if "phone" in title.lower() else "input_code.txt"
    print(f"\n⚠️ Terminal input not available. Please type the value in: {filename}")
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            f.write("")
    
    input_val = ""
    while not input_val:
        import time
        time.sleep(2)
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                input_val = f.read().strip()
    return input_val

def phone_cb():
    return get_user_input("Telegram Login", "Enter your phone number (e.g. +919876543210):")

def code_cb():
    return get_user_input("Telegram Verification Code", "Enter the code sent to your Telegram app:")

def password_cb():
    return get_user_input("2-Step Verification", "Enter your 2FA password (leave blank if none):")

def main():
    print("=" * 60)
    print("  TELEGRAM SESSION STRING GENERATOR")
    print("=" * 60)
    print("Connecting with API ID: 32751734...")

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    
    try:
        client.start(
            phone=phone_cb,
            code_callback=code_cb,
            password=password_cb
        )
    except Exception as e:
        print(f"\n❌ Login failed: {e}")
        return

    session_str = client.session.save()
    print("\n" + "=" * 60)
    print("🎉 SUCCESS! HERE IS YOUR TELEGRAM_SESSION_STRING:")
    print("=" * 60)
    print(session_str)
    print("=" * 60)

    # Save to file
    out_file = os.path.join(os.path.dirname(__file__), ".session_string.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(session_str)
    print(f"\n✅ Automatically saved to {out_file}")

if __name__ == "__main__":
    main()
