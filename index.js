const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const bodyParser = require('body-parser');

const app = express();
app.use(bodyParser.json());

let isReady = false;
let qrData = null;

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        executablePath: '/usr/bin/google-chrome-stable',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-extensions',
            '--disable-software-rasterizer',
            '--mute-audio'
        ]
    }
});

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    qrData = qr;
    console.log('QR Code generated - scan with WhatsApp');
});

client.on('ready', () => {
    isReady = true;
    qrData = null;
    console.log('\n\x1b[42m\x1b[30m ✅ WHATSAPP CONNECTED! \x1b[0m');
    console.log('\x1b[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m');
    console.log('\x1b[32m  WhatsApp client is ready to send!  \x1b[0m');
    console.log('\x1b[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m\n');
});

client.on('disconnected', () => {
    isReady = false;
    console.log('WhatsApp disconnected');
    client.initialize();
});

client.initialize();

app.get('/status', (req, res) => {
    res.json({ ready: isReady, qr: qrData });
});

app.post('/send', async (req, res) => {
    const { phone, message } = req.body;
    if (!isReady) return res.status(503).json({ error: 'WhatsApp not ready' });
    if (!phone || !message) return res.status(400).json({ error: 'phone and message required' });

    try {
        const chatId = phone.replace('+', '') + '@c.us';
        await client.sendMessage(chatId, message);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

const PORT = 3001;
app.listen(PORT, () => console.log(`WhatsApp bridge running on port ${PORT}`));
