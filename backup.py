#!/usr/bin/env python3

import os
import subprocess
import shutil
import zipfile
import logging
import sys
import json
import urllib.request
from datetime import datetime
from pathlib import Path
import tempfile

from config import (
    MONGODB_URI, BACKUP_DIR, LOG_FILE, MAX_BACKUP_SIZE_GB,
    MONGODUMP_PATH, get_backup_filename, ensure_directories,
    MIN_FREE_SPACE_GB, ESTIMATED_BACKUP_SIZE_GB,
    BACKUP_SPACE_MULTIPLIER, MIN_DUMP_SIZE_FACTOR_VS_LARGEST_ZIP,
    ZIP_OUTPUT_MAX_FACTOR, MIN_BACKUPS_TO_KEEP,
    SYSTEM_CLEANUP_ENABLED, JOURNAL_VACUUM_SIZE, APT_CLEAN_ENABLED,
    LOCAL_LOG_FILES_TO_TRIM, MAX_LOCAL_LOG_TRIM_MB,
)
SLACK_WEBHOOK_URL = "SLACK_WEBHOOK"

def send_slack_message(message, is_error=True):
    if not SLACK_WEBHOOK_URL:
        return
    try:
        if is_error:
            payload = {"text": f":x: *MongoDB Backup Alert*\n{message}"}
        else:
            payload = {"text": f":white_check_mark: *MongoDB Backup Success*\n{message}"}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(SLACK_WEBHOOK_URL, data=data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logging.error(f"Failed to send Slack message: {str(e)}")

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

def get_disk_free_space_gb(path):
    stat = os.statvfs(path)
    return (stat.f_bavail * stat.f_frsize) / (1024 ** 3)

def get_backup_files_sorted():
    backup_files = []
    if not os.path.exists(BACKUP_DIR):
        return backup_files
    for filename in os.listdir(BACKUP_DIR):
        if filename.endswith('.zip'):
            filepath = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(filepath):
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath) / (1024 ** 3)
                backup_files.append((mtime, filepath, filename, size))
    backup_files.sort(key=lambda x: x[0])
    return backup_files

def get_largest_backup_zip_size_gb():
    backup_files = get_backup_files_sorted()
    if not backup_files:
        return 0.0
    return max(x[3] for x in backup_files)

def compute_required_space_before_dump():
    largest = get_largest_backup_zip_size_gb()
    data_need = max(
        ESTIMATED_BACKUP_SIZE_GB,
        largest * BACKUP_SPACE_MULTIPLIER,
        largest * MIN_DUMP_SIZE_FACTOR_VS_LARGEST_ZIP,
    )
    return MIN_FREE_SPACE_GB + data_need

def trim_local_logs():
    if not LOCAL_LOG_FILES_TO_TRIM or MAX_LOCAL_LOG_TRIM_MB <= 0:
        return
    limit_bytes = int(MAX_LOCAL_LOG_TRIM_MB * 1024 * 1024)
    cwd = os.getcwd()
    for rel in LOCAL_LOG_FILES_TO_TRIM:
        path = rel if os.path.isabs(rel) else os.path.join(cwd, rel)
        try:
            if os.path.isfile(path) and os.path.getsize(path) > limit_bytes:
                with open(path, "w", encoding="utf-8"):
                    pass
                logging.info(f"Truncated oversized log file: {rel}")
        except OSError as e:
            logging.warning(f"Could not trim log {rel}: {e}")

def run_system_disk_cleanup():
    if not SYSTEM_CLEANUP_ENABLED:
        return
    before = get_disk_free_space_gb(BACKUP_DIR)
    trim_local_logs()
    if shutil.which("journalctl"):
        r = subprocess.run(
            ["journalctl", "--vacuum-size", JOURNAL_VACUUM_SIZE],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if r.returncode != 0:
            logging.warning(f"journalctl vacuum returned {r.returncode}: {r.stderr or r.stdout}")
    if APT_CLEAN_ENABLED and shutil.which("apt-get"):
        subprocess.run(
            ["apt-get", "clean"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    after = get_disk_free_space_gb(BACKUP_DIR)
    gained = after - before
    if gained > 0.01:
        logging.info(f"System cleanup: ~{gained:.2f} GB freed (free space now {after:.2f} GB)")

def cleanup_old_backups():
    if not os.path.exists(BACKUP_DIR):
        return
    
    current_size = get_directory_size_gb(BACKUP_DIR)
    logging.info(f"Current backup directory size: {current_size:.2f} GB")
    
    if current_size <= MAX_BACKUP_SIZE_GB:
        logging.info("Backup directory size is within limit")
        return
    
    backup_files = get_backup_files_sorted()
    
    removed_count = 0
    while current_size > MAX_BACKUP_SIZE_GB and len(backup_files) > MIN_BACKUPS_TO_KEEP:
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
    final_size = get_directory_size_gb(BACKUP_DIR)
    if final_size > MAX_BACKUP_SIZE_GB and len(get_backup_files_sorted()) <= MIN_BACKUPS_TO_KEEP:
        logging.warning(
            f"Backup directory still over size limit ({final_size:.2f} GB > {MAX_BACKUP_SIZE_GB} GB); "
            f"keeping at least {MIN_BACKUPS_TO_KEEP} backup file(s)"
        )

def ensure_disk_space(required_gb, min_backups_to_keep=0):
    free_space = get_disk_free_space_gb(BACKUP_DIR)
    logging.info(f"Current free disk space: {free_space:.2f} GB, required: {required_gb:.2f} GB")
    
    if free_space >= required_gb:
        return True
    
    run_system_disk_cleanup()
    free_space = get_disk_free_space_gb(BACKUP_DIR)
    logging.info(f"Free disk space after system cleanup: {free_space:.2f} GB (required: {required_gb:.2f} GB)")
    if free_space >= required_gb:
        return True
    
    backup_files = get_backup_files_sorted()
    
    removed_count = 0
    while free_space < required_gb and len(backup_files) > min_backups_to_keep:
        mtime, filepath, filename, size = backup_files.pop(0)
        try:
            os.remove(filepath)
            removed_count += 1
            logging.info(f"Removed old backup for disk space: {filename} ({size:.2f} GB)")
            free_space = get_disk_free_space_gb(BACKUP_DIR)
        except Exception as e:
            logging.error(f"Failed to remove {filename}: {str(e)}")
    
    if removed_count > 0:
        logging.info(f"Disk space cleanup completed. Removed {removed_count} files. Free space: {free_space:.2f} GB")
    if free_space < required_gb and min_backups_to_keep > 0:
        logging.error(
            f"Need {required_gb:.2f} GB free but only {free_space:.2f} GB available; "
            f"stopped deleting backups (minimum retained: {min_backups_to_keep})"
        )
    
    return free_space >= required_gb

def get_temp_directory():
    tmp_free = get_disk_free_space_gb("/tmp")
    if tmp_free >= ESTIMATED_BACKUP_SIZE_GB:
        return tempfile.mkdtemp()
    
    logging.warning(f"/tmp has only {tmp_free:.2f} GB free, using backup directory for temp storage")
    temp_path = os.path.join(BACKUP_DIR, "temp_dump")
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)
    os.makedirs(temp_path)
    return temp_path

def create_mongodb_backup():
    backup_name = get_backup_filename()
    temp_dir = get_temp_directory()
    dump_path = os.path.join(temp_dir, backup_name)
    
    try:
        logging.info(f"Starting MongoDB backup: {backup_name}")
        logging.info(f"Using temp directory: {temp_dir}")
        
        cmd = [MONGODUMP_PATH, "--uri", MONGODB_URI, "--out", dump_path]
        logging.info("Running mongodump...")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode != 0:
            error_msg = result.stderr.strip().split('\n')[-1] if result.stderr else "Unknown error"
            raise Exception(f"mongodump failed (exit code {result.returncode}): {error_msg}")
        
        logging.info("MongoDB dump completed successfully")

        dump_gb = get_directory_size_gb(dump_path)
        zip_space_estimate = dump_gb * ZIP_OUTPUT_MAX_FACTOR
        need_before_zip = MIN_FREE_SPACE_GB + zip_space_estimate
        if not ensure_disk_space(need_before_zip, MIN_BACKUPS_TO_KEEP):
            raise Exception(
                f"Insufficient disk space before zip (dump ~{dump_gb:.2f} GB, "
                f"need ~{need_before_zip:.2f} GB free for zip + margin; expand disk or lower retention)"
            )
        
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
        send_slack_message("Backup timed out after 1 hour")
        return None
    except Exception as e:
        logging.error(f"Backup failed: {str(e)}")
        send_slack_message(f"Backup failed: {str(e)}")
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
        run_system_disk_cleanup()
        
        required_space = compute_required_space_before_dump()
        if not ensure_disk_space(required_space, MIN_BACKUPS_TO_KEEP):
            msg = f"Insufficient disk space. Need at least {required_space:.2f} GB free"
            logging.error(msg)
            send_slack_message(msg)
            return 1
        
        backup_path = create_mongodb_backup()
        
        if backup_path:
            zip_size = os.path.getsize(backup_path) / (1024 ** 2)
            logging.info("Backup process completed successfully")
            send_slack_message(f"Backup completed: {os.path.basename(backup_path)} ({zip_size:.1f} MB)", is_error=False)
            return 0
        else:
            logging.error("Backup process failed")
            return 1
            
    except KeyboardInterrupt:
        logging.info("Backup process interrupted by user")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        send_slack_message(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
