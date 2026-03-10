# sendmsg — WhatsApp Automator

Schedule and send WhatsApp messages from a web dashboard. Runs fully headless on Ubuntu Server — no GUI needed.

## Features
- 📤 Send messages instantly
- ⏰ Schedule messages for later
- 🖥️ Web dashboard to manage everything
- 🤖 Fully headless via whatsapp-web.js

## Requirements
- Ubuntu Server 20.04+
- Root or sudo access

## Installation

```bash
git clone https://github.com/tekeia/sendmsg.git
cd sendmsg
chmod +x install.sh start.sh
sudo ./install.sh
```

## Usage

```bash
./start.sh
```

Open your browser: `http://YOUR_SERVER_IP:5000`

On first run a **QR code** will appear in the terminal.
Scan it with WhatsApp → Linked Devices → Link a Device.
Session is saved — no need to scan again after that.

## Project Structure

```
sendmsg/
├── app.py                  # Flask backend + scheduler
├── requirements.txt        # Python dependencies
├── install.sh              # One-command installer
├── start.sh                # Start all services
├── templates/
│   └── index.html          # Web dashboard
└── whatsapp/
    ├── index.js            # Headless WhatsApp bridge
    └── package.json        # Node dependencies
```
