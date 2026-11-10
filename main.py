import os
import sys
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiohttp import web

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TelegramAutoApprover")

# --- Configuration & Environment Variables ---
API_ID_ENV = os.environ.get("TELEGRAM_API_ID", "32751734")
API_HASH = os.environ.get("TELEGRAM_API_HASH", "6107561583effd9e9d245e7a46e839a4")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING")

# Target chat/bot filter: Locked strictly to @Harshtradebot
TARGET_CHAT = os.environ.get("TARGET_CHAT", "@Harshtradebot").strip()

# Keywords to match on button text (comma-separated, case-insensitive)
# Supports "[ ✅ ALLOW ]", "ALLOW", "APPROVE", etc.
KEYWORDS_RAW = os.environ.get("APPROVE_KEYWORDS", "allow,approve,confirm").lower()
APPROVE_KEYWORDS = [k.strip() for k in KEYWORDS_RAW.split(",") if k.strip()]

# SAFETY SWITCH: Kept FALSE by default until you explicitly instruct to enable it!
# When FALSE: it detects and logs buttons but DOES NOT CLICK them.
# When TRUE: it clicks matching buttons automatically.
AUTO_APPROVE_ENABLED = os.environ.get("AUTO_APPROVE_ENABLED", "false").lower() in ("true", "1", "yes")

if not API_ID_ENV or not API_HASH:
    logger.error("Missing API_ID or API_HASH!")
    sys.exit(1)

try:
    API_ID = int(API_ID_ENV)
except ValueError:
    logger.error("TELEGRAM_API_ID must be an integer!")
    sys.exit(1)

# Check session string
if not SESSION_STRING:
    # Try reading from local .session_string.txt if present
    local_file = os.path.join(os.path.dirname(__file__), ".session_string.txt")
    if os.path.exists(local_file):
        with open(local_file, "r", encoding="utf-8") as f:
            SESSION_STRING = f.read().strip()

if not SESSION_STRING:
    logger.error("Missing TELEGRAM_SESSION_STRING! Run generate_session.py first.")
    sys.exit(1)

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage(chats=TARGET_CHAT if TARGET_CHAT else None))
async def on_new_message(event):
    message = event.message
    
    # We only care about messages that have inline keyboard buttons
    if not message.buttons:
        return

    chat_title = getattr(event.chat, 'title', None) or getattr(event.chat, 'username', None) or str(event.chat_id)
    preview_text = (message.text or "").replace("\n", " ")[:60]
    logger.info(f"📩 Button message received from [{chat_title}]: \"{preview_text}...\"")

    # Iterate through all buttons
    for row in message.buttons:
        for button in row:
            button_label = (button.text or "").strip().lower()
            
            # Check if any approve keyword matches the button label
            if any(kw in button_label for kw in APPROVE_KEYWORDS):
                global AUTO_APPROVE_ENABLED
                if not AUTO_APPROVE_ENABLED:
                    logger.warning(
                        f"⏸️ SAFETY PAUSE ACTIVE: Found button '{button.text}', "
                        f"but auto-clicking is DISABLED. Standing by."
                    )
                    return

                logger.info(f"⚡ Match found! Button label: '{button.text}'. Attempting click...")
                try:
                    await button.click()
                    logger.info(f"✅ Successfully clicked button: '{button.text}'")
                    return
                except Exception as err:
                    logger.error(f"❌ Failed to click button '{button.text}': {err}")

# Endpoint to toggle auto-approve on/off dynamically via HTTP
async def toggle_approver(request):
    global AUTO_APPROVE_ENABLED
    action = request.query.get("action", "").lower()
    if action == "enable":
        AUTO_APPROVE_ENABLED = True
    elif action == "disable":
        AUTO_APPROVE_ENABLED = False
    
    status = "ENABLED" if AUTO_APPROVE_ENABLED else "DISABLED (PAUSED)"
    return web.Response(text=f"Auto-Approver status: {status}\n")

# Health check
async def health_check(request):
    status = "ENABLED" if AUTO_APPROVE_ENABLED else "PAUSED (SAFE MODE)"
    return web.Response(text=f"OK - Service is alive. Mode: {status}\n", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    app.router.add_get("/toggle", toggle_approver)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Keep-Alive HTTP server listening on 0.0.0.0:{port}")

async def main():
    await start_web_server()
    await client.start()
    me = await client.get_me()
    logger.info(f"🎉 Telegram client authenticated as: {me.first_name} (@{me.username or me.phone})")
    
    mode_str = "🟢 ACTIVE (WILL CLICK)" if AUTO_APPROVE_ENABLED else "🟡 PAUSED (SAFETY MODE - WILL NOT CLICK)"
    logger.info(f"Current State: {mode_str}")
    logger.info(f"Listening for buttons matching keywords: {APPROVE_KEYWORDS}")
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
