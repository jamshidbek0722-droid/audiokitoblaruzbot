import os
import sys
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID_RAW = os.getenv("OWNER_ID", "0")
STORAGE_CHANNEL_ID_RAW = os.getenv("STORAGE_CHANNEL_ID", "0")

MONGO_URI = os.getenv("MONGO_URI", "")

OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW.strip().replace("-", "").isdigit() else 0
STORAGE_CHANNEL_ID = int(STORAGE_CHANNEL_ID_RAW) if STORAGE_CHANNEL_ID_RAW.strip().replace("-", "").isdigit() else 0
REQUIRED_CHANNEL_IDS = []  # Can also be dynamically loaded/saved in index

# AI API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


