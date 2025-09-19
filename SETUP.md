# MongoDB Daily Backup Setup Instructions

## Prerequisites

### On Ubuntu/Debian:
```bash
sudo apt update
sudo apt install python3 mongodb-database-tools cron
```

### On CentOS/RHEL:
```bash
sudo yum install python3 mongodb-database-tools cronie
sudo systemctl enable crond
sudo systemctl start crond
```

## Installation & Configuration

1. **Clone/Upload this project to your Linux server**

2. **Configure MongoDB Connection**
   
   Edit `config.py` and update the MongoDB URI variables:
   ```python
   # Source MongoDB (for backups)
   MONGODB_URI = "mongodb://username:password@localhost:27017/database_name"
   
   # Target MongoDB (for restores) - REQUIRED for restore operations
   TARGET_MONGODB_URI = "mongodb://username:password@target-server:27017/database_name"
   ```
   
   Examples:
   - Local MongoDB: `"mongodb://localhost:27017"`
   - Remote MongoDB: `"mongodb://user:pass@192.168.1.100:27017"`
   - MongoDB Atlas: `"mongodb+srv://user:pass@cluster.mongodb.net/"`
   
   **Important**: `TARGET_MONGODB_URI` must be configured for restore operations to work. This allows you to restore backups to a different MongoDB instance than the source.

3. **Set up directory permissions**
   ```bash
   chmod +x backup.py restore.py setup_cron.sh
   ```

4. **Test the backup manually**
   ```bash
   python3 backup.py
   ```

5. **Set up daily cron job**
   ```bash
   ./setup_cron.sh
   ```

## Usage

### Manual Backup
```bash
python3 backup.py
```

### List Available Backups
```bash
python3 restore.py --list
```

### Restore a Backup
```bash
python3 restore.py mongodb_backup_20241201_120000
```

### View Logs
```bash
tail -f backup.log
```

## Configuration Options

Edit `config.py` to customize:

- `MONGODB_URI`: Source MongoDB connection string (for backups)
- `TARGET_MONGODB_URI`: Target MongoDB connection string (for restores) - **REQUIRED**
- `BACKUP_DIR`: Directory to store backups (default: "backups")
- `LOG_FILE`: Log file path (default: "backup.log")
- `MAX_BACKUP_SIZE_GB`: Maximum size of backup directory in GB (default: 5)
- `MONGODUMP_PATH`: Path to mongodump binary (default: "mongodump")
- `MONGORESTORE_PATH`: Path to mongorestore binary (default: "mongorestore")

## Features

✅ **Daily Automated Backups**: Runs at 2:00 AM daily via cron
✅ **Size Management**: Automatically removes old backups when directory exceeds 5GB
✅ **Date-Named Backups**: Backup files include timestamp (e.g., `mongodb_backup_20241201_120000.zip`)
✅ **Compressed Storage**: All backups are compressed using ZIP
✅ **Easy Restore**: Simple command-line restore by backup name
✅ **Comprehensive Logging**: All operations logged with timestamps
✅ **Error Handling**: Robust error handling and timeout protection

## Troubleshooting

### Check if mongodump is available:
```bash
which mongodump
mongodump --version
```

### Check cron job status:
```bash
crontab -l
sudo systemctl status cron
```

### View cron logs:
```bash
tail -f backup_cron.log
```

### Test MongoDB connection:
```bash
mongodump --uri "your_mongodb_uri" --dry-run
```

## File Structure

```
mongodb-daily-backup/
├── backup.py          # Main backup script
├── restore.py         # Restore script
├── config.py          # Configuration settings
├── setup_cron.sh      # Cron job setup script
├── requirements.txt   # System requirements
├── SETUP.md          # This file
├── backup.log        # Application logs (created after first run)
├── backup_cron.log   # Cron execution logs (created after first cron run)
└── backups/          # Backup storage directory (created automatically)
    ├── mongodb_backup_20241201_020000.zip
    ├── mongodb_backup_20241202_020000.zip
    └── ...
```
