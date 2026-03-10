#!/bin/bash

# Get the directory where this script lives
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Starting WPP Automator..."
echo ""
echo "[1/2] Starting WhatsApp bridge (port 3001)..."
echo "      Scan the QR code below with WhatsApp."
echo "      Once connected, Flask will start automatically."
echo ""

# Start bridge in background but keep output visible
node "$DIR/whatsapp/index.js" &
BRIDGE_PID=$!

# Wait until bridge is up on port 3001
for i in $(seq 1 30); do
    if curl -s http://localhost:3001/status > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Start Flask app
echo ""
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
echo "  Press Ctrl+C to stop."
echo ""

trap "echo 'Stopping...'; kill $BRIDGE_PID $FLASK_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
