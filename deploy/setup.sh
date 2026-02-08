#!/bin/bash
# Hetzner VPS setup script for Topic Tracker
# Run as root on a fresh Ubuntu 24.04 ARM server (CAX21)
#
# Usage:
#   scp deploy/setup.sh root@<server-ip>:~/setup.sh
#   ssh root@<server-ip> "chmod +x setup.sh && ./setup.sh"
#
# After running, you still need to:
#   1. Create Backend/.env with your secrets (see Backend/.env.example)
#   2. Edit /etc/caddy/Caddyfile with your domain
#   3. Run: sudo systemctl reload caddy
#   4. Run: sudo systemctl start topic-tracker

set -euo pipefail

REPO_URL="${1:-}"
DEPLOY_USER="deploy"
APP_DIR="/home/$DEPLOY_USER/topic-tracker"

if [ -z "$REPO_URL" ]; then
    echo "Usage: ./setup.sh <git-repo-url>"
    echo "Example: ./setup.sh https://github.com/youruser/topic-tracker.git"
    exit 1
fi

echo "=== System updates ==="
apt update && apt upgrade -y

echo "=== Creating deploy user ==="
if ! id "$DEPLOY_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" "$DEPLOY_USER"
    usermod -aG sudo "$DEPLOY_USER"
    # Allow passwordless sudo for deploy user
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$DEPLOY_USER
    # Copy SSH keys
    mkdir -p /home/$DEPLOY_USER/.ssh
    cp ~/.ssh/authorized_keys /home/$DEPLOY_USER/.ssh/
    chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
    chmod 700 /home/$DEPLOY_USER/.ssh
    chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys
fi

echo "=== Installing system dependencies ==="
apt install -y python3 python3-venv python3-pip git curl

echo "=== Cloning repository ==="
sudo -u $DEPLOY_USER git clone "$REPO_URL" "$APP_DIR" || {
    echo "Repo already exists, pulling latest..."
    sudo -u $DEPLOY_USER bash -c "cd $APP_DIR && git pull"
}

echo "=== Setting up Python venv ==="
sudo -u $DEPLOY_USER python3 -m venv "$APP_DIR/venv"
sudo -u $DEPLOY_USER bash -c "source $APP_DIR/venv/bin/activate && pip install --upgrade pip && pip install -r $APP_DIR/Backend/requirements.txt"

echo "=== Pre-caching sentence-transformer model ==="
sudo -u $DEPLOY_USER bash -c "source $APP_DIR/venv/bin/activate && python -c \"from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')\""

echo "=== Installing systemd service ==="
cp "$APP_DIR/deploy/topic-tracker.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable topic-tracker

echo "=== Installing Caddy ==="
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install -y caddy

echo "=== Copying Caddyfile template ==="
cp "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile

echo ""
echo "========================================="
echo "  Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Create the .env file:"
echo "     cp $APP_DIR/Backend/.env.example $APP_DIR/Backend/.env"
echo "     nano $APP_DIR/Backend/.env"
echo ""
echo "  2. Initialize the database:"
echo "     sudo -u $DEPLOY_USER bash -c 'source $APP_DIR/venv/bin/activate && cd $APP_DIR/Backend && python init_db.py && python seed_specs.py'"
echo ""
echo "  3. Edit the Caddyfile with your domain:"
echo "     nano /etc/caddy/Caddyfile"
echo "     systemctl reload caddy"
echo ""
echo "  4. Start the service:"
echo "     systemctl start topic-tracker"
echo ""
echo "  5. Verify:"
echo "     curl http://localhost:8000/docs"
echo "     systemctl status topic-tracker"
echo ""
