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
API_ID_ENV = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING")

# Target chat/bot filter (Optional). If None, listens to all incoming messages with buttons.
TARGET_CHAT = os.environ.get("TARGET_CHAT", "").strip() or None

# Keywords to match on button text (comma-separated, case-insensitive)
# e.g. "approve,allow,confirm,yes,accept"
KEYWORDS_RAW = os.environ.get("APPROVE_KEYWORDS", "approve,allow,confirm").lower()
APPROVE_KEYWORDS = [k.strip() for k in KEYWORDS_RAW.split(",") if k.strip()]

if not API_ID_ENV or not API_HASH or not SESSION_STRING:
    logger.error("Missing required environment variables!")
    logger.error("Please set TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_SESSION_STRING.")
    sys.exit(1)

try:
    API_ID = int(API_ID_ENV)
except ValueError:
    logger.error("TELEGRAM_API_ID must be an integer!")
    sys.exit(1)

# Initialize Telethon Client with StringSession
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

    # Iterate through all buttons (rows and columns)
    for row_idx, row in enumerate(message.buttons):
        for col_idx, button in enumerate(row):
            button_label = (button.text or "").strip().lower()
            
            # Check if any approve keyword matches the button label
            if any(kw in button_label for kw in APPROVE_KEYWORDS):
                logger.info(f"⚡ Match found! Button label: '{button.text}'. Attempting click...")
                try:
                    await button.click()
                    logger.info(f"✅ Successfully clicked button: '{button.text}'")
                    return
                except Exception as err:
                    logger.error(f"❌ Failed to click button '{button.text}': {err}")

# --- Render Port Binding & Health Check HTTP Server ---
async def health_check(request):
    return web.Response(
        text="OK - Telegram Auto-Approver is live and listening.",
        status=200,
        content_type="text/plain"
    )

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    app.router.add_get("/readyz", health_check)

    runner = web.AppRunner(app)
    await runner.setup()

    # Render injects $PORT (usually 10000). Fallback to 10000 if not set.
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Keep-Alive HTTP server listening on 0.0.0.0:{port} (Render port check satisfied)")

async def main():
    logger.info("Starting Render Keep-Alive HTTP server...")
    await start_web_server()

    logger.info("Connecting Telegram client via StringSession...")
    await client.start()
    me = await client.get_me()
    logger.info(f"🎉 Telegram client authenticated as: {me.first_name} (@{me.username or me.phone})")
    logger.info(f"Listening for buttons matching keywords: {APPROVE_KEYWORDS}")
    if TARGET_CHAT:
        logger.info(f"Filter active: Only listening to chat '{TARGET_CHAT}'")
    else:
        logger.info("Listening to ALL incoming chats for approve buttons.")

    # Run Telethon event loop continuously
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
