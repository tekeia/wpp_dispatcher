#!/bin/bash
set -e

# Get the directory where this script lives
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "======================================"
echo "   WPP Automator - Install Script"
echo "======================================"

# Fix folder structure if files are in root
echo "[0/6] Setting up folder structure..."
mkdir -p "$DIR/whatsapp"
mkdir -p "$DIR/templates"

# Move index.js to whatsapp/ if it's in root
if [ -f "$DIR/index.js" ] && [ ! -f "$DIR/whatsapp/index.js" ]; then
    mv "$DIR/index.js" "$DIR/whatsapp/index.js"
    echo "  Moved index.js -> whatsapp/index.js"
fi

# Move index.html to templates/ if it's in root
if [ -f "$DIR/index.html" ] && [ ! -f "$DIR/templates/index.html" ]; then
    mv "$DIR/index.html" "$DIR/templates/index.html"
    echo "  Moved index.html -> templates/index.html"
fi

# Create package.json if missing
if [ ! -f "$DIR/whatsapp/package.json" ]; then
    cat > "$DIR/whatsapp/package.json" << 'EOF'
{
  "name": "wpp-bridge",
  "version": "1.0.0",
  "description": "WhatsApp Web bridge",
  "main": "index.js",
  "scripts": {
    "start": "node index.js"
  },
  "dependencies": {
    "whatsapp-web.js": "^1.23.0",
    "qrcode-terminal": "^0.12.0",
    "express": "^4.18.2",
    "body-parser": "^1.20.2"
  }
}
EOF
    echo "  Created whatsapp/package.json"
fi

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

# Fix permissions — sudo may have changed ownership of files
echo "Fixing permissions..."
chown -R $(logname):$(logname) "$DIR"

echo ""
echo "======================================"
echo "   Installation Complete!"
echo "======================================"
echo ""
echo "To start the app run:  ./start.sh"
echo ""

