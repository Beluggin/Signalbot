#!/usr/bin/env bash
# ============================================================
# SignalBot Home Base — Server Setup Script
# Run this on the Ubuntu/Debian laptop as your normal user.
# ============================================================
set -e

APPDIR="$HOME/signalbot-home"
VENV="$APPDIR/.venv"
PASS="${SIGNALBOT_PASS:-signals2026}"   # change via env var or edit here
SECRET="${SECRET_KEY:-$(python3 -c 'import secrets; print(secrets.token_hex(32))')}"

echo ""
echo "══════════════════════════════════════════"
echo "  SignalBot Home Base — Setup"
echo "══════════════════════════════════════════"
echo ""

# ── 1. System deps ────────────────────────────────────────────
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv nginx curl

# ── 2. Python venv ────────────────────────────────────────────
echo "[2/6] Creating Python venv..."
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q flask gunicorn

# ── 3. Environment file ───────────────────────────────────────
echo "[3/6] Writing .env file..."
cat > "$APPDIR/.env" <<EOF
SECRET_KEY=$SECRET
SIGNALBOT_PASS=$PASS
EOF
chmod 600 "$APPDIR/.env"
echo "    Passphrase set to: $PASS"
echo "    (Edit $APPDIR/.env to change it)"

# ── 4. Systemd service ────────────────────────────────────────
echo "[4/6] Creating systemd service..."
sudo tee /etc/systemd/system/signalbot.service > /dev/null <<EOF
[Unit]
Description=SignalBot Home Base
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APPDIR
EnvironmentFile=$APPDIR/.env
ExecStart=$VENV/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable signalbot
sudo systemctl restart signalbot
echo "    Service started."

# ── 5. Nginx reverse proxy ────────────────────────────────────
echo "[5/6] Configuring nginx..."
sudo tee /etc/nginx/sites-available/signalbot > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # WebSocket support (for future use)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/signalbot /etc/nginx/sites-enabled/signalbot
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
echo "    Nginx configured."

# ── 6. Cloudflare Quick Tunnel ────────────────────────────────
echo "[6/6] Installing cloudflared..."

# Download cloudflared binary
CF_BIN="/usr/local/bin/cloudflared"
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
elif [ "$ARCH" = "aarch64" ]; then
    CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
else
    CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-386"
fi

if [ ! -f "$CF_BIN" ]; then
    sudo curl -sL "$CF_URL" -o "$CF_BIN"
    sudo chmod +x "$CF_BIN"
fi

# Systemd service for tunnel
sudo tee /etc/systemd/system/cloudflared-tunnel.service > /dev/null <<EOF
[Unit]
Description=Cloudflare Quick Tunnel for SignalBot
After=network.target signalbot.service

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:80 --no-autoupdate
Restart=always
RestartSec=10
# URL is printed to stdout — check with: journalctl -u cloudflared-tunnel -f

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloudflared-tunnel
sudo systemctl restart cloudflared-tunnel

echo ""
echo "══════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Your public URL will appear in:"
echo "  journalctl -u cloudflared-tunnel -f"
echo "  (look for trycloudflare.com link)"
echo ""
echo "  Passphrase: $PASS"
echo "  Local:      http://localhost"
echo ""
echo "  To update passphrase:"
echo "  nano $APPDIR/.env"
echo "  sudo systemctl restart signalbot"
echo "══════════════════════════════════════════"
