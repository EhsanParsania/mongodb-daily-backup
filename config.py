import os
from datetime import datetime

MONGODB_URI = "MONGODB"
TARGET_MONGODB_URI = "MONGO_URI"
BACKUP_DIR = "backups"
LOG_FILE = "backup.log"
MAX_BACKUP_SIZE_GB = 5
MIN_FREE_SPACE_GB = 1.0
ESTIMATED_BACKUP_SIZE_GB = 1.0
BACKUP_SPACE_MULTIPLIER = 2.5
MIN_DUMP_SIZE_FACTOR_VS_LARGEST_ZIP = 12.0
ZIP_OUTPUT_MAX_FACTOR = 1.05
MIN_BACKUPS_TO_KEEP = 3
SYSTEM_CLEANUP_ENABLED = True
JOURNAL_VACUUM_SIZE = "100M"
APT_CLEAN_ENABLED = False
LOCAL_LOG_FILES_TO_TRIM = ("backup_cron.log",)
MAX_LOCAL_LOG_TRIM_MB = 30
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
