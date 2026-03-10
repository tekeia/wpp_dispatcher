#!/bin/bash

# Get the directory where this script lives
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Starting WPP Automator..."

# Start WhatsApp bridge in background
echo "[1/2] Starting WhatsApp bridge (port 3001)..."
cd "$DIR/whatsapp"
node index.js &
BRIDGE_PID=$!
cd "$DIR"

# Wait for bridge to initialize
sleep 2

# Start Flask app
echo "[2/2] Starting Flask dashboard (port 5000)..."
source "$DIR/venv/bin/activate"
python3 "$DIR/app.py" &
FLASK_PID=$!

echo ""
echo "======================================"
echo "  WPP Automator is running!"
echo "======================================"
echo ""
echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "  A QR code will appear below — scan it"
echo "  with WhatsApp to connect."
echo ""
echo "  Press Ctrl+C to stop."
echo ""

trap "echo 'Stopping...'; kill $BRIDGE_PID $FLASK_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
