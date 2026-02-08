#!/bin/bash
# Quick deploy script — run after pushing code changes
# Usage: ssh deploy@<server-ip> "~/topic-tracker/deploy/deploy.sh"

set -euo pipefail

APP_DIR="/home/deploy/topic-tracker"

cd "$APP_DIR"

echo "=== Pulling latest code ==="
git pull

echo "=== Installing any new dependencies ==="
source venv/bin/activate
pip install -r Backend/requirements.txt --quiet

echo "=== Restarting service ==="
sudo systemctl restart topic-tracker

echo "=== Waiting for startup ==="
sleep 3

if systemctl is-active --quiet topic-tracker; then
    echo "Deploy successful! Service is running."
else
    echo "WARNING: Service failed to start. Check logs:"
    echo "  journalctl -u topic-tracker -n 50"
    exit 1
fi
