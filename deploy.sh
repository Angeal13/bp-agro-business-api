#!/bin/bash
# BP-Agro-IoT — Deploy Script
# Installs: bpagro-iot (Flask API, port 5000)
set -e
DEPLOY_DIR="/home/ubuntu/bp-agro-iot"
VENV="$DEPLOY_DIR/venv"
echo "=============================="
echo "  BP Agro IoT — Deploy v3"
echo "=============================="

echo "[1/5] System packages..."
sudo apt-get update -q
sudo apt-get install -y python3.11 python3.11-venv nginx mysql-client curl

echo "[2/5] Virtual environment..."
[ ! -d "$VENV" ] && python3.11 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$DEPLOY_DIR/requirements.txt" -q

echo "[3/5] Checking .env..."
[ ! -f "$DEPLOY_DIR/.env" ] && { cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
  echo "  WARNING: .env created from example — fill in credentials"; read -rp "  Press Enter when done: " _; }

echo "[4/5] Systemd service..."
sudo cp "$DEPLOY_DIR/services/bpagro-iot.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bpagro-iot
sudo systemctl restart bpagro-iot
sleep 2
STATUS=$(systemctl is-active bpagro-iot)
[ "$STATUS" = "active" ] && echo "  OK  bpagro-iot" || { echo "  FAIL  bpagro-iot — $STATUS"; sudo journalctl -u bpagro-iot -n 20 --no-pager; }

echo "[5/5] Nginx..."
sudo tee /etc/nginx/sites-available/bpagro-iot > /dev/null << 'NGINX'
server {
    listen 80;
    server_name _;
    location /api/global/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }
}
NGINX
sudo ln -sf /etc/nginx/sites-available/bpagro-iot /etc/nginx/sites-enabled/bpagro-iot
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=============================="
echo "  Done. IoT API: port 5000"
echo "  Logs: journalctl -u bpagro-iot -f"
echo "=============================="
