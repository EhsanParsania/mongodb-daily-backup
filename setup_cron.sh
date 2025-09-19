#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH=$(which python3)

if [ -z "$PYTHON_PATH" ]; then
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

echo "Setting up daily MongoDB backup cron job..."
echo "Script directory: $SCRIPT_DIR"
echo "Python path: $PYTHON_PATH"

CRON_COMMAND="0 2 * * * cd $SCRIPT_DIR && $PYTHON_PATH backup.py >> backup_cron.log 2>&1"

echo "Adding cron job: $CRON_COMMAND"

(crontab -l 2>/dev/null | grep -v "backup.py"; echo "$CRON_COMMAND") | crontab -

if [ $? -eq 0 ]; then
    echo "✓ Cron job added successfully!"
    echo "  - Backup will run daily at 2:00 AM"
    echo "  - Logs will be written to backup.log and backup_cron.log"
    echo ""
    echo "To view current cron jobs: crontab -l"
    echo "To remove the cron job: crontab -e (then delete the backup.py line)"
else
    echo "✗ Failed to add cron job"
    exit 1
fi
