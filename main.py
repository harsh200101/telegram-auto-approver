import os
import sys
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiohttp import web

# Set up logging to stdout with immediate flush
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger("TelegramAutoApprover")

# --- Configuration & Environment Variables ---
API_ID_ENV = os.environ.get("TELEGRAM_API_ID", "32751734")
API_HASH = os.environ.get("TELEGRAM_API_HASH", "6107561583effd9e9d245e7a46e839a4")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING")

# Target chat/bot filter
TARGET_CHAT = os.environ.get("TARGET_CHAT", "@Harshtradebot").strip()

# Keywords to match on button text (comma-separated, case-insensitive)
KEYWORDS_RAW = os.environ.get("APPROVE_KEYWORDS", "allow,approve,confirm").lower()
APPROVE_KEYWORDS = [k.strip() for k in KEYWORDS_RAW.split(",") if k.strip()]

# SAFETY SWITCH: Default False (paused)
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
    local_file = os.path.join(os.path.dirname(__file__), ".session_string.txt")
    if os.path.exists(local_file):
        with open(local_file, "r", encoding="utf-8") as f:
            SESSION_STRING = f.read().strip()

if not SESSION_STRING:
    logger.error("Missing TELEGRAM_SESSION_STRING! Run generate_session.py first.")
    sys.exit(1)

# Initialize Telethon Client with StringSession
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage)
async def on_new_message(event):
    # Only process messages that have inline buttons
    message = event.message
    if not message or not message.buttons:
        return

    # Filter by target chat/bot if configured
    if TARGET_CHAT:
        sender = await event.get_sender()
        sender_username = getattr(sender, "username", "") or ""
        chat_title = getattr(event.chat, "title", "") or ""
        chat_id_str = str(event.chat_id)
        
        target_clean = TARGET_CHAT.lstrip("@").lower()
        matches_username = sender_username.lower() == target_clean
        matches_title = target_clean in chat_title.lower()
        matches_id = chat_id_str == target_clean
        
        if not (matches_username or matches_title or matches_id):
            return

    sender_name = getattr(event.chat, 'title', None) or getattr(event.chat, 'username', None) or str(event.chat_id)
    preview = (message.text or "").replace("\n", " ")[:60]
    logger.info(f"📩 Target button message received from [{sender_name}]: \"{preview}...\"")

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
                        f"but AUTO_APPROVE_ENABLED is false. Not clicking."
                    )
                    return

                logger.info(f"⚡ Matching button found: '{button.text}'. Attempting click...")
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
    
    status = "ENABLED (ACTIVE)" if AUTO_APPROVE_ENABLED else "DISABLED (PAUSED)"
    return web.Response(text=f"Auto-Approver status: {status}\n")

# Health check
async def health_check(request):
    status = "ACTIVE" if AUTO_APPROVE_ENABLED else "PAUSED (SAFE MODE)"
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
    # 1. Start HTTP server first so Render port-binding passes immediately
    await start_web_server()

    # 2. Connect client using pre-authorized StringSession (Never prompts for input!)
    logger.info("Connecting to Telegram via StringSession...")
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("❌ Session string is not authorized! Please re-generate session string.")
        sys.exit(1)

    me = await client.get_me()
    logger.info(f"🎉 Telegram client connected as: {me.first_name} (@{me.username or me.phone})")
    
    mode_str = "🟢 ACTIVE (WILL CLICK)" if AUTO_APPROVE_ENABLED else "🟡 PAUSED (SAFETY MODE - WILL NOT CLICK)"
    logger.info(f"Current State: {mode_str}")
    logger.info(f"Target chat: {TARGET_CHAT}")
    logger.info(f"Keywords: {APPROVE_KEYWORDS}")

    # 3. Run continuously
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
