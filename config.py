import os
from datetime import datetime

MONGODB_URI = "mongodb://localhost:27017"
TARGET_MONGODB_URI = ""
BACKUP_DIR = "backups"
LOG_FILE = "backup.log"
MAX_BACKUP_SIZE_GB = 5
MONGODUMP_PATH = "mongodump"
MONGORESTORE_PATH = "mongorestore"

def get_backup_filename():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"mongodb_backup_{timestamp}"

def ensure_directories():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    logs_dir = os.path.dirname(LOG_FILE)
    if logs_dir and not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
