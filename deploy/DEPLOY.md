# Deployment

## Frontend (Vercel)

Vercel auto-deploys when a push is detected to `main`.

## Backend (Hetzner VPS)

The backend runs on a Hetzner VPS as a systemd service at `/root/topic-classifier`.

### Quick redeploy after pushing to main

SSH in and run the deploy script:

```bash
ssh root@46.225.15.193 "/root/topic-classifier/deploy/deploy.sh"
```

This pulls the latest code, installs any new dependencies, and restarts the service.

### Manual redeploy

```bash
ssh root@46.225.15.193
cd /root/topic-classifier
git pull
source venv/bin/activate
pip install -r Backend/requirements.txt
systemctl restart topic-tracker
```

### Checking status

```bash
# Service status
systemctl status topic-tracker

# Live logs
journalctl -u topic-tracker -f

# Recent logs
journalctl -u topic-tracker -n 50
```

### To redeploy systemd service file

```bash
cp deploy/topic-tracker.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart topic-tracker
```
