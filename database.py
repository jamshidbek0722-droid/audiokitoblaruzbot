import logging
import asyncio
from datetime import datetime
from aiogram import Bot
import motor.motor_asyncio
import config

logger = logging.getLogger(__name__)

# In-memory RAM caches (source of truth for reads)
admins = set()             # Set of admin user IDs (integers)
categories = {}            # cat_id -> {id: str, name: str, status: str}
books = {}                 # book_id -> {id: str, title: str, author: str, description: str, category: str, audio_file_id: str, audio_message_id: int, pdf_file_id: str, cover_file_id: str, source: str, status: str}
users = {}                 # user_id -> {id: int, username: str, full_name: str, favorites: list, history: list, joined_at: str}
recommendations = {}       # rec_id -> {id: str, user_id: int, title: str, author: str, description: str, category: str, audio_file_id: str, cover_file_id: str, pdf_file_id: str, status: str}
settings = {
    "mandatory_subscription": False,
    "custom_footer": "",
    "categories_columns": 2,
    "books_sorting": "upload_time",
    "categories_order": []
}
required_channels = {}     # channel_id -> {id: int, title: str, url: str}

# MongoDB clients and collections
db_client = None
db = None

users_col = None
books_col = None
categories_col = None
recommendations_col = None
settings_col = None
required_channels_col = None
admins_col = None

# Lock to avoid concurrent database writes
save_lock = asyncio.Lock()

async def load_index(bot: Bot):
    """
    Initializes connection to MongoDB Atlas, retrieves all collections,
    and populates the in-memory RAM caches.
    """
    global db_client, db, users_col, books_col, categories_col, recommendations_col, settings_col, required_channels_col, admins_col
    
    try:
        logger.info("Initializing MongoDB connection using MONGO_URI...")
        db_client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
        # Select database named 'audiokitoblar_db'
        db = db_client["audiokitoblar_db"]
        
        # Setup collection objects
        users_col = db["users"]
        books_col = db["books"]
        categories_col = db["categories"]
        recommendations_col = db["recommendations"]
        settings_col = db["settings"]
        required_channels_col = db["required_channels"]
        admins_col = db["admins"]
        
        logger.info("Loading MongoDB data into RAM cache (clean slate/fresh load)...")
        
        # 1. Load Admins
        admins.clear()
        async for doc in admins_col.find():
            admins.add(int(doc["_id"]))
        admins.add(config.OWNER_ID)
        
        # Always ensure the main owner is stored in MongoDB
        await admins_col.update_one(
            {"_id": config.OWNER_ID},
            {"$set": {"user_id": config.OWNER_ID}},
            upsert=True
        )
        
        # 2. Load Categories
        categories.clear()
        async for doc in categories_col.find():
            cat_id = doc["_id"]
            # Exclude _id to keep clean schema matching old logic
            doc_copy = doc.copy()
            del doc_copy["_id"]
            categories[cat_id] = doc_copy
            
        # 3. Load Books
        books.clear()
        async for doc in books_col.find():
            book_id = doc["_id"]
            doc_copy = doc.copy()
            del doc_copy["_id"]
            books[book_id] = doc_copy
            
        # 4. Load Users
        users.clear()
        async for doc in users_col.find():
            user_id = int(doc["_id"])
            doc_copy = doc.copy()
            del doc_copy["_id"]
            users[user_id] = doc_copy
            
        # 5. Load Recommendations
        recommendations.clear()
        async for doc in recommendations_col.find():
            rec_id = doc["_id"]
            doc_copy = doc.copy()
            del doc_copy["_id"]
            recommendations[rec_id] = doc_copy
            
        # 6. Load Settings
        settings_doc = await settings_col.find_one({"_id": "global"})
        settings.clear()
        if settings_doc:
            settings_copy = settings_doc.copy()
            del settings_copy["_id"]
            settings.update(settings_copy)
        else:
            # Initialize with default settings
            settings.update({
                "mandatory_subscription": False,
                "custom_footer": "",
                "categories_columns": 2,
                "books_sorting": "upload_time",
                "categories_order": []
            })
            await settings_col.update_one(
                {"_id": "global"},
                {"$set": settings},
                upsert=True
            )
            
        # 7. Load Required Channels
        required_channels.clear()
        async for doc in required_channels_col.find():
            channel_id = int(doc["_id"])
            doc_copy = doc.copy()
            del doc_copy["_id"]
            required_channels[channel_id] = doc_copy
            
        logger.info(f"MongoDB data successfully synchronized. Cache contents: Admins: {len(admins)}, Users: {len(users)}, Books: {len(books)}, Categories: {len(categories)}, Channels: {len(required_channels)}")
    except Exception as e:
        logger.critical(f"FATAL ERROR: Failed to load MongoDB data: {e}", exc_info=True)
        # Fallback to local default state
        admins.clear()
        admins.add(config.OWNER_ID)

async def save_index(bot: Bot):
    """
    Synchronizes all in-memory caches to the MongoDB collections.
    This replaces the old storage channel pinned message index file.
    """
    if db is None:
        logger.warning("MongoDB database is not initialized. Cannot sync RAM to DB.")
        return

    async with save_lock:
        try:
            logger.info("Saving in-memory changes to MongoDB Atlas collections...")
            
            # 1. Sync Admins (upsert all, delete removed)
            for admin_id in admins:
                await admins_col.update_one(
                    {"_id": admin_id},
                    {"$set": {"user_id": admin_id}},
                    upsert=True
                )
            await admins_col.delete_many({"_id": {"$nin": list(admins)}})
            
            # 2. Sync Categories
            for cat_id, cat_data in categories.items():
                await categories_col.update_one(
                    {"_id": cat_id},
                    {"$set": cat_data},
                    upsert=True
                )
            await categories_col.delete_many({"_id": {"$nin": list(categories.keys())}})
            
            # 3. Sync Books
            for book_id, book_data in books.items():
                await books_col.update_one(
                    {"_id": book_id},
                    {"$set": book_data},
                    upsert=True
                )
            await books_col.delete_many({"_id": {"$nin": list(books.keys())}})
            
            # 4. Sync Users
            for user_id, user_data in users.items():
                user_data["_id"] = int(user_id)
                user_data["id"] = int(user_id)
                await users_col.update_one(
                    {"_id": int(user_id)},
                    {"$set": user_data},
                    upsert=True
                )
            await users_col.delete_many({"_id": {"$nin": [int(k) for k in users.keys()]}})
            
            # 5. Sync Recommendations
            for rec_id, rec_data in recommendations.items():
                await recommendations_col.update_one(
                    {"_id": rec_id},
                    {"$set": rec_data},
                    upsert=True
                )
            await recommendations_col.delete_many({"_id": {"$nin": list(recommendations.keys())}})
            
            # 6. Sync Settings
            settings_to_save = settings.copy()
            if "_id" in settings_to_save:
                del settings_to_save["_id"]
            await settings_col.update_one(
                {"_id": "global"},
                {"$set": settings_to_save},
                upsert=True
            )
            
            # 7. Sync Required Channels
            for ch_id, ch_data in required_channels.items():
                await required_channels_col.update_one(
                    {"_id": int(ch_id)},
                    {"$set": ch_data},
                    upsert=True
                )
            await required_channels_col.delete_many({"_id": {"$nin": [int(k) for k in required_channels.keys()]}})
            
            logger.info("Successfully synchronized all modifications to MongoDB Atlas.")
        except Exception as e:
            logger.error(f"Error saving RAM caches to MongoDB Atlas: {e}", exc_info=True)

def is_admin(user_id: int) -> bool:
    """Checks if user is in admin list."""
    return user_id == config.OWNER_ID or user_id in admins

async def register_user(user_id: int, username: str, full_name: str, bot: Bot):
    """Registers user in RAM and instantly updates MongoDB."""
    user_id = int(user_id)
    if user_id not in users:
        users[user_id] = {
            "id": user_id,
            "username": username or "",
            "full_name": full_name or "",
            "favorites": [],
            "history": [],
            "profile": None,
            "listening_stats": {"total_seconds": 0, "completed_books": []},
            "joined_at": datetime.now().isoformat()
        }
    else:
        if users[user_id].get("username") != username:
            users[user_id]["username"] = username or ""
        if users[user_id].get("full_name") != full_name:
            users[user_id]["full_name"] = full_name or ""
        if "listening_stats" not in users[user_id]:
            users[user_id]["listening_stats"] = {"total_seconds": 0, "completed_books": []}
            
    # Instantly persist registration details
    if users_col is not None:
        try:
            user_data = users[user_id].copy()
            user_data["_id"] = user_id
            await users_col.update_one(
                {"_id": user_id},
                {"$set": user_data},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save user registration to MongoDB: {e}")
