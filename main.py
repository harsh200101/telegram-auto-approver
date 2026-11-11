import os
import sys
import asyncio
import logging
import traceback
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiohttp import web

# Set up logging with immediate flush
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

# Target chat/bot filter: locked to @Harshtradebot
TARGET_CHAT = os.environ.get("TARGET_CHAT", "@Harshtradebot").strip()

# Keywords to match on button text (comma-separated, case-insensitive)
KEYWORDS_RAW = os.environ.get("APPROVE_KEYWORDS", "allow,approve,confirm").lower()
APPROVE_KEYWORDS = [k.strip() for k in KEYWORDS_RAW.split(",") if k.strip()]

# AUTO_APPROVE_ENABLED defaults to True
AUTO_APPROVE_ENABLED = os.environ.get("AUTO_APPROVE_ENABLED", "true").lower() in ("true", "1", "yes")

telegram_client = None

# Statistics tracker
stats = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "messages_received": 0,
    "target_messages_matched": 0,
    "buttons_detected": 0,
    "buttons_clicked": 0,
    "last_clicked_at": None,
    "last_clicked_text": None,
    "recent_events": []
}

def log_event(event_type, details):
    entry = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "type": event_type,
        "details": details
    }
    stats["recent_events"].insert(0, entry)
    if len(stats["recent_events"]) > 20:
        stats["recent_events"].pop()

async def on_new_message(event):
    message = event.message
    if not message:
        return

    stats["messages_received"] += 1

    # Only process messages that have inline buttons
    if not message.buttons:
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

    stats["target_messages_matched"] += 1
    sender_name = getattr(event.chat, 'title', None) or getattr(event.chat, 'username', None) or str(event.chat_id)
    preview = (message.text or "").replace("\n", " ")[:60]
    logger.info(f"📩 Target button message received from [{sender_name}]: \"{preview}...\"")
    log_event("MESSAGE_RECEIVED", f"From {sender_name}: {preview}")

    # Scan buttons
    for row in message.buttons:
        for button in row:
            stats["buttons_detected"] += 1
            button_label = (button.text or "").strip().lower()
            
            if any(kw in button_label for kw in APPROVE_KEYWORDS):
                global AUTO_APPROVE_ENABLED
                if not AUTO_APPROVE_ENABLED:
                    logger.warning(
                        f"⏸️ SAFETY PAUSE ACTIVE: Found button '{button.text}', "
                        f"but AUTO_APPROVE_ENABLED is false. Not clicking."
                    )
                    log_event("PAUSED_SKIPPED", f"Button '{button.text}' seen but auto-approve is disabled.")
                    return

                logger.info(f"⚡ Matching button found: '{button.text}'. Clicking now...")
                try:
                    await button.click()
                    stats["buttons_clicked"] += 1
                    stats["last_clicked_at"] = datetime.now(timezone.utc).isoformat()
                    stats["last_clicked_text"] = button.text
                    logger.info(f"✅ Successfully clicked button: '{button.text}' (Total clicked: {stats['buttons_clicked']})")
                    log_event("BUTTON_CLICKED", f"Successfully clicked '{button.text}'")
                    return
                except Exception as err:
                    logger.error(f"❌ Failed to click button '{button.text}': {err}")
                    log_event("CLICK_ERROR", f"Error on '{button.text}': {str(err)}")

# Ultra-lightweight ping handler (returns 2 bytes "OK" to satisfy cron-job limits)
async def ping_handler(request):
    if request.method == "HEAD":
        return web.Response(status=200, headers={"Content-Length": "0"})
    return web.Response(text="OK", content_type="text/plain", status=200)

async def toggle_approver(request):
    global AUTO_APPROVE_ENABLED
    action = request.query.get("action", "").lower()
    if action == "enable":
        AUTO_APPROVE_ENABLED = True
    elif action == "disable":
        AUTO_APPROVE_ENABLED = False
    
    status = "ENABLED (ACTIVE)" if AUTO_APPROVE_ENABLED else "DISABLED (PAUSED)"
    log_event("MODE_TOGGLE", f"Switched to {status}")
    return web.Response(text=f"Auto-Approver status: {status}\n")

# Stats endpoint (JSON)
async def stats_endpoint(request):
    data = {
        "status": "ACTIVE" if AUTO_APPROVE_ENABLED else "PAUSED",
        "target_chat": TARGET_CHAT,
        "keywords": APPROVE_KEYWORDS,
        "stats": stats
    }
    return web.json_response(data)

async def start_web_server():
    app = web.Application()
    # Support both GET and HEAD for pinging
    app.router.add_route("*", "/", ping_handler)
    app.router.add_route("*", "/ping", ping_handler)
    app.router.add_route("*", "/health", ping_handler)
    app.router.add_get("/stats", stats_endpoint)
    app.router.add_get("/toggle", toggle_approver)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Ultra-light Keep-Alive HTTP server listening on 0.0.0.0:{port}")

async def main():
    global telegram_client
    
    # 1. Start HTTP server FIRST so Render port-binding succeeds immediately
    await start_web_server()

    # 2. Validate configuration
    if not API_ID_ENV or not API_HASH:
        logger.error("Missing API_ID or API_HASH!")
        sys.exit(1)

    api_id = int(API_ID_ENV)
    session_str = SESSION_STRING

    if not session_str:
        local_file = os.path.join(os.path.dirname(__file__), ".session_string.txt")
        if os.path.exists(local_file):
            with open(local_file, "r", encoding="utf-8") as f:
                session_str = f.read().strip()

    if not session_str:
        logger.error("Missing TELEGRAM_SESSION_STRING!")
        sys.exit(1)

    # 3. Instantiate TelegramClient INSIDE the running asyncio loop
    logger.info("Initializing Telegram client inside async loop...")
    telegram_client = TelegramClient(StringSession(session_str), api_id, API_HASH)
    
    # 4. Attach event handler
    telegram_client.add_event_handler(on_new_message, events.NewMessage())

    # 5. Connect
    logger.info("Connecting to Telegram...")
    await telegram_client.connect()

    if not await telegram_client.is_user_authorized():
        logger.error("❌ Session string is not authorized!")
        sys.exit(1)

    me = await telegram_client.get_me()
    logger.info(f"🎉 Telegram client connected as: {me.first_name} (@{me.username or me.phone})")
    
    mode_str = "🟢 ACTIVE (WILL CLICK)" if AUTO_APPROVE_ENABLED else "🟡 PAUSED (SAFETY MODE - WILL NOT CLICK)"
    logger.info(f"Current State: {mode_str}")
    logger.info(f"Target chat: {TARGET_CHAT}")
    logger.info(f"Keywords: {APPROVE_KEYWORDS}")

    # 6. Run continuously
    await telegram_client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}\n{traceback.format_exc()}")
        sys.exit(1)
