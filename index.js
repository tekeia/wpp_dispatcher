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
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-gpu'
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
    console.log('WhatsApp client is ready!');
});

client.on('disconnected', () => {
    isReady = false;
    console.log('WhatsApp disconnected');
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
