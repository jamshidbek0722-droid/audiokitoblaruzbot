import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

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
        # We still continue, but database operations might fail if channel is inaccessible.
        
    # 2. Rebuild index from storage channel
    await database.load_index(bot)
    logger.info("Bot is ready and polling updates.")

async def main():
    # Initialize Bot
    bot = Bot(token=config.BOT_TOKEN)
    
    # Initialize Dispatcher with MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register subscription verification middleware
    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())
    
    # Include routers in priority order:
    # 1. Admin router (intercepts admin menu commands)
    # 2. User router (general user queries, FSM search, book menus)
    # 3. Common router (start, help, basic handlers)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(common_router)
    
    # Register startup hook
    dp.startup.register(on_startup)
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
