#!/usr/bin/env python3

import os
import subprocess
import shutil
import zipfile
import logging
import sys
from datetime import datetime
from pathlib import Path
import tempfile

from config import (
    MONGODB_URI, BACKUP_DIR, LOG_FILE, MAX_BACKUP_SIZE_GB,
    MONGODUMP_PATH, get_backup_filename, ensure_directories
)

def setup_logging():
    ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_directory_size_gb(directory):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size / (1024 ** 3)

def cleanup_old_backups():
    if not os.path.exists(BACKUP_DIR):
        return
    
    current_size = get_directory_size_gb(BACKUP_DIR)
    logging.info(f"Current backup directory size: {current_size:.2f} GB")
    
    if current_size <= MAX_BACKUP_SIZE_GB:
        logging.info("Backup directory size is within limit")
        return
    
    backup_files = []
    for filename in os.listdir(BACKUP_DIR):
        if filename.endswith('.zip'):
            filepath = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(filepath):
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath) / (1024 ** 3)
                backup_files.append((mtime, filepath, filename, size))
    
    backup_files.sort(key=lambda x: x[0])
    
    removed_count = 0
    while current_size > MAX_BACKUP_SIZE_GB and backup_files:
        mtime, filepath, filename, size = backup_files.pop(0)
        try:
            os.remove(filepath)
            current_size -= size
            removed_count += 1
            logging.info(f"Removed old backup: {filename} ({size:.2f} GB)")
        except Exception as e:
            logging.error(f"Failed to remove {filename}: {str(e)}")
    
    if removed_count > 0:
        final_size = get_directory_size_gb(BACKUP_DIR)
        logging.info(f"Cleanup completed. Removed {removed_count} files. New size: {final_size:.2f} GB")

def create_mongodb_backup():
    backup_name = get_backup_filename()
    temp_dir = tempfile.mkdtemp()
    dump_path = os.path.join(temp_dir, backup_name)
    
    try:
        logging.info(f"Starting MongoDB backup: {backup_name}")
        
        cmd = [MONGODUMP_PATH, "--uri", MONGODB_URI, "--out", dump_path]
        logging.info(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode != 0:
            raise Exception(f"mongodump failed: {result.stderr}")
        
        logging.info("MongoDB dump completed successfully")
        
        zip_filename = f"{backup_name}.zip"
        zip_path = os.path.join(BACKUP_DIR, zip_filename)
        
        logging.info(f"Creating zip archive: {zip_filename}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(dump_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)
        
        zip_size = os.path.getsize(zip_path) / (1024 ** 3)
        logging.info(f"Backup created successfully: {zip_filename} ({zip_size:.2f} GB)")
        
        return zip_path
        
    except subprocess.TimeoutExpired:
        logging.error("MongoDB backup timed out after 1 hour")
        return None
    except Exception as e:
        logging.error(f"Backup failed: {str(e)}")
        return None
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.debug(f"Cleaned up temporary directory: {temp_dir}")

def main():
    try:
        setup_logging()
        ensure_directories()
        
        logging.info("=" * 50)
        logging.info("Starting daily MongoDB backup process")
        logging.info("=" * 50)
        
        cleanup_old_backups()
        
        backup_path = create_mongodb_backup()
        
        if backup_path:
            logging.info("Backup process completed successfully")
            return 0
        else:
            logging.error("Backup process failed")
            return 1
            
    except KeyboardInterrupt:
        logging.info("Backup process interrupted by user")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
