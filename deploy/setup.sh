#!/usr/bin/env bash
# One-time setup on a fresh Debian/Ubuntu VM (e.g. GCP e2-micro).
# Usage:  sudo bash deploy/setup.sh   (run from the cloned kudos-bot directory,
#         after creating a .env file with SLACK_BOT_TOKEN, SLACK_APP_TOKEN, KUDOS_CHANNEL)
set -euo pipefail

if [ ! -f .env ]; then
  echo "ERROR: create a .env file first (see README), then re-run."
  exit 1
fi

apt-get update -y
apt-get install -y python3-venv

# dedicated unprivileged user
id -u kudos &>/dev/null || useradd --system --home /opt/kudos-bot --shell /usr/sbin/nologin kudos

# install the app to /opt/kudos-bot
mkdir -p /opt/kudos-bot
cp -r app.py templates.yaml requirements.txt .env /opt/kudos-bot/
cd /opt/kudos-bot
python3 -m venv .venv
.venv/bin/pip install --quiet -r requirements.txt
chown -R kudos:kudos /opt/kudos-bot
chmod 600 /opt/kudos-bot/.env

# systemd service: start now and on every boot
cp "$(dirname "$0")/kudos-bot.service" /etc/systemd/system/ 2>/dev/null \
  || cp /opt/kudos-bot/deploy/kudos-bot.service /etc/systemd/system/ 2>/dev/null \
  || { echo "copying unit from repo"; cp ~/kudos-bot/deploy/kudos-bot.service /etc/systemd/system/; }
systemctl daemon-reload
systemctl enable --now kudos-bot

sleep 3
systemctl --no-pager status kudos-bot || true
echo
echo "Done. Logs: sudo journalctl -u kudos-bot -f"
