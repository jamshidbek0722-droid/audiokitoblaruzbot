import json
import io
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import BufferedInputFile
from config import STORAGE_CHANNEL_ID, OWNER_ID

logger = logging.getLogger(__name__)

# In-memory structures
admins = set()             # Set of admin user IDs (integers)
categories = {}            # cat_id -> {id: str, name: str, status: str}
books = {}                 # book_id -> {id: str, title: str, author: str, description: str, category: str, audio_file_id: str, audio_message_id: int, pdf_file_id: str, cover_file_id: str, source: str, status: str}
users = {}                 # user_id -> {id: int, username: str, full_name: str, favorites: list, history: list, joined_at: str}
recommendations = {}       # rec_id -> {id: str, user_id: int, title: str, author: str, description: str, category: str, audio_file_id: str, cover_file_id: str, pdf_file_id: str, status: str}
settings = {"mandatory_subscription": False}
required_channels = {}     # channel_id -> {id: int, title: str, url: str}

# Lock to avoid concurrent index writes
import asyncio
save_lock = asyncio.Lock()

async def save_index(bot: Bot):
    async with save_lock:
        try:
            data = {
                "admins": list(admins),
                "categories": categories,
                "books": books,
                "users": {str(k): v for k, v in users.items()},
                "recommendations": recommendations,
                "settings": settings,
                "required_channels": {str(k): v for k, v in required_channels.items()}
            }
            
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            input_file = BufferedInputFile(bytes(json_str, "utf-8"), filename="index.json")
            
            # Fetch old pinned message to delete it afterwards
            old_pin_id = None
            try:
                chat = await bot.get_chat(chat_id=STORAGE_CHANNEL_ID)
                if chat.pinned_message:
                    old_pin_id = chat.pinned_message.message_id
            except Exception as e:
                logger.warning(f"Could not fetch pinned message: {e}")
            
            # Upload new index file
            msg = await bot.send_document(
                chat_id=STORAGE_CHANNEL_ID,
                document=input_file,
                caption="#INDEX\nUshbu xabar bot ma'lumotlar bazasi indeksini saqlaydi. Iltimos, o'chirmang."
            )
            
            # Pin the new index file
            await bot.pin_chat_message(chat_id=STORAGE_CHANNEL_ID, message_id=msg.message_id)
            
            # Delete old pinned index message to avoid spam
            if old_pin_id:
                try:
                    await bot.delete_message(chat_id=STORAGE_CHANNEL_ID, message_id=old_pin_id)
                except Exception as e:
                    logger.warning(f"Could not delete old pinned index message: {e}")
                    
            logger.info("Successfully saved and pinned the index to the storage channel.")
        except Exception as e:
            logger.error(f"Error saving index to storage channel: {e}", exc_info=True)

async def load_index(bot: Bot):
    global admins, categories, books, users, recommendations, settings, required_channels
    
    try:
        logger.info("Connecting to storage channel to retrieve index...")
        chat = await bot.get_chat(chat_id=STORAGE_CHANNEL_ID)
        pinned = chat.pinned_message
        
        if pinned and pinned.document:
            file_id = pinned.document.file_id
            file = await bot.get_file(file_id)
            
            dest = io.BytesIO()
            await bot.download_file(file.file_path, dest)
            dest.seek(0)
            
            data = json.loads(dest.read().decode("utf-8"))
            
            # Populate in-memory structures
            admins = set(data.get("admins", []))
            admins.add(OWNER_ID) # Always ensure main owner is admin
            
            categories = data.get("categories", {})
            books = data.get("books", {})
            
            # Parse user keys to integers
            raw_users = data.get("users", {})
            users = {int(k): v for k, v in raw_users.items()}
            
            recommendations = data.get("recommendations", {})
            settings = data.get("settings", {"mandatory_subscription": False})
            
            # Parse required channel keys to integers
            raw_req = data.get("required_channels", {})
            required_channels = {int(k): v for k, v in raw_req.items()}
            
            logger.info("Database index loaded successfully.")
        else:
            logger.warning("No pinned message found in storage channel. Initializing new database index...")
            admins.add(OWNER_ID)
            await save_index(bot)
    except Exception as e:
        logger.error(f"Error loading database index: {e}", exc_info=True)
        # Initialize default state
        admins.add(OWNER_ID)
        try:
            await save_index(bot)
        except Exception as init_err:
            logger.critical(f"Failed to initialize clean index: {init_err}")

def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in admins

async def register_user(user_id: int, username: str, full_name: str, bot: Bot):
    if user_id not in users:
        users[user_id] = {
            "id": user_id,
            "username": username or "",
            "full_name": full_name or "",
            "favorites": [],
            "history": [],
            "joined_at": datetime.now().isoformat()
        }
        await save_index(bot)
    else:
        updated = False
        if users[user_id].get("username") != username:
            users[user_id]["username"] = username or ""
            updated = True
        if users[user_id].get("full_name") != full_name:
            users[user_id]["full_name"] = full_name or ""
            updated = True
        if updated:
            await save_index(bot)
