import os
import sys
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID")
STORAGE_CHANNEL_ID_RAW = os.getenv("STORAGE_CHANNEL_ID")

if not BOT_TOKEN or not OWNER_ID_RAW or not STORAGE_CHANNEL_ID_RAW:
    print("FATAL ERROR: BOT_TOKEN, OWNER_ID, and STORAGE_CHANNEL_ID must be set in the .env file or environment!")
    sys.exit(1)

OWNER_ID = int(OWNER_ID_RAW)
STORAGE_CHANNEL_ID = int(STORAGE_CHANNEL_ID_RAW)
REQUIRED_CHANNEL_IDS = []  # Can also be dynamically loaded/saved in index
