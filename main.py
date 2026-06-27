import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

import config
import database
from handlers.common import router as common_router, SubscriptionMiddleware
from handlers.user import router as user_router
from handlers.admin import router as admin_router

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Dummy web server handler for Render health checks
async def handle_health(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    
    # Render allocates a port dynamically via the PORT environment variable
    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Dummy health check web server started on port {port}")

async def on_startup(bot: Bot):
    logger.info("Bot starting up...")
    
    # 1. Verify storage channel access
    try:
        chat = await bot.get_chat(chat_id=config.STORAGE_CHANNEL_ID)
        logger.info(f"Connected to storage channel: {chat.title} (ID: {config.STORAGE_CHANNEL_ID})")
    except Exception as e:
        logger.critical(
            f"Could not connect to STORAGE_CHANNEL_ID: {config.STORAGE_CHANNEL_ID}. "
            f"Please verify that the ID is correct and the bot is added as an administrator to the channel!\n"
            f"Error: {e}"
        )
        
    # 2. Rebuild index from storage channel
    await database.load_index(bot)
    logger.info("Bot is ready and polling updates.")

async def main():
    # Verify environment configurations before bot initialization
    if not config.BOT_TOKEN or config.OWNER_ID == 0 or config.STORAGE_CHANNEL_ID == 0 or not config.MONGO_URI:
        logger.critical(
            "FATAL CONFIG ERROR: BOT_TOKEN, OWNER_ID, STORAGE_CHANNEL_ID, and MONGO_URI "
            "must be properly set in the environment variables before starting the bot!"
        )
        sys.exit(1)

    # Initialize Bot
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    
    # Initialize Dispatcher with MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register subscription verification middleware
    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())
    
    # Include routers in priority order
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(common_router)
    
    # Register startup hook
    dp.startup.register(on_startup)
    
    # Run both the dummy web server (for Render) and aiogram polling concurrently
    await asyncio.gather(
        start_web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
