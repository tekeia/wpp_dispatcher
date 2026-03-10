#!/bin/bash
set -e

echo "======================================"
echo "   WPP Automator - Install Script"
echo "======================================"

# Update system
echo "[1/6] Updating system..."
apt-get update -y

# Install Node.js
echo "[2/6] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Google Chrome
echo "[3/6] Installing Google Chrome..."
apt-get install -y wget gnupg ca-certificates
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt-get update -y
apt-get install -y google-chrome-stable

# Install Python
echo "[4/6] Installing Python..."
apt-get install -y python3 python3-pip python3-venv

# Setup Python venv
echo "[5/6] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup Node WhatsApp bridge
echo "[6/6] Setting up WhatsApp bridge..."
cd whatsapp
npm install
cd ..

echo ""
echo "======================================"
echo "   Installation Complete!"
echo "======================================"
echo ""
echo "To start the app run:  ./start.sh"
echo ""
