#!/usr/bin/env python3

import os
import subprocess
import shutil
import zipfile
import logging
import sys
import tempfile
from pathlib import Path

from config import (
    MONGODB_URI, TARGET_MONGODB_URI, BACKUP_DIR, LOG_FILE, MONGORESTORE_PATH, ensure_directories
)

def setup_logging():
    ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def list_available_backups():
    if not os.path.exists(BACKUP_DIR):
        logging.error(f"Backup directory '{BACKUP_DIR}' does not exist")
        return []
    
    backups = []
    for filename in os.listdir(BACKUP_DIR):
        if filename.endswith('.zip'):
            filepath = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath) / (1024 ** 2)
                mtime = os.path.getmtime(filepath)
                backups.append({
                    'filename': filename,
                    'path': filepath,
                    'size_mb': size,
                    'mtime': mtime
                })
    
    backups.sort(key=lambda x: x['mtime'], reverse=True)
    return backups

def restore_mongodb_backup(backup_name):
    if not backup_name.endswith('.zip'):
        backup_name += '.zip'
    
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    if not os.path.exists(backup_path):
        logging.error(f"Backup file not found: {backup_path}")
        return False
    
    if not TARGET_MONGODB_URI or TARGET_MONGODB_URI.strip() == "":
        logging.error("TARGET_MONGODB_URI is not configured. Please set the target MongoDB URI in config.py")
        return False
    
    temp_dir = tempfile.mkdtemp()
    extract_path = os.path.join(temp_dir, "restore")
    
    try:
        logging.info(f"Starting restore from backup: {backup_name}")
        logging.info(f"Target MongoDB URI: {TARGET_MONGODB_URI}")
        
        logging.info("Extracting backup archive...")
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(extract_path)
        
        dump_dirs = []
        for item in os.listdir(extract_path):
            item_path = os.path.join(extract_path, item)
            if os.path.isdir(item_path):
                dump_dirs.append(item_path)
        
        if not dump_dirs:
            raise Exception("No database directories found in backup")
        
        restore_path = dump_dirs[0] if len(dump_dirs) == 1 else extract_path
        
        logging.info("Starting MongoDB restore...")
        cmd = [MONGORESTORE_PATH, "--uri", TARGET_MONGODB_URI, "--drop", restore_path]
        logging.info(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode != 0:
            raise Exception(f"mongorestore failed: {result.stderr}")
        
        logging.info("MongoDB restore completed successfully")
        logging.info(f"Restore output: {result.stdout}")
        
        return True
        
    except subprocess.TimeoutExpired:
        logging.error("MongoDB restore timed out after 1 hour")
        return False
    except Exception as e:
        logging.error(f"Restore failed: {str(e)}")
        return False
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.debug(f"Cleaned up temporary directory: {temp_dir}")

def main():
    if len(sys.argv) < 2:
        setup_logging()
        
        print("\nMongoDB Backup Restore Tool")
        print("=" * 40)
        print("Usage: python restore.py <backup_name>")
        print("       python restore.py --list")
        print("\nAvailable commands:")
        print("  --list    Show all available backups")
        print("  <name>    Restore specific backup (with or without .zip extension)")
        print("\nExamples:")
        print("  python restore.py mongodb_backup_20241201_120000")
        print("  python restore.py mongodb_backup_20241201_120000.zip")
        print("  python restore.py --list")
        
        backups = list_available_backups()
        if backups:
            print(f"\nAvailable backups in '{BACKUP_DIR}':")
            print("-" * 60)
            for backup in backups:
                from datetime import datetime
                date_str = datetime.fromtimestamp(backup['mtime']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  {backup['filename']:<40} {backup['size_mb']:.1f} MB  {date_str}")
        else:
            print(f"\nNo backups found in '{BACKUP_DIR}'")
        
        return 0
    
    setup_logging()
    
    command = sys.argv[1]
    
    if command == "--list":
        backups = list_available_backups()
        if backups:
            print(f"\nAvailable backups in '{BACKUP_DIR}':")
            print("-" * 60)
            for backup in backups:
                from datetime import datetime
                date_str = datetime.fromtimestamp(backup['mtime']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  {backup['filename']:<40} {backup['size_mb']:.1f} MB  {date_str}")
        else:
            print(f"No backups found in '{BACKUP_DIR}'")
        return 0
    
    try:
        logging.info("=" * 50)
        logging.info("Starting MongoDB restore process")
        logging.info("=" * 50)
        
        if restore_mongodb_backup(command):
            logging.info("Restore process completed successfully")
            return 0
        else:
            logging.error("Restore process failed")
            return 1
            
    except KeyboardInterrupt:
        logging.info("Restore process interrupted by user")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
