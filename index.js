const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const express = require('express');
const bodyParser = require('body-parser');
const qrcode = require('qrcode-terminal');
const P = require('pino');

const app = express();
app.use(bodyParser.json());

let sock = null;
let isReady = false;
let qrData = null;

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info');

    sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        logger: P({ level: 'silent' })
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            qrData = qr;
            qrcode.generate(qr, { small: true });
            console.log('QR Code generated - scan with WhatsApp');
        }

        if (connection === 'close') {
            isReady = false;
            qrData = null;
            const shouldReconnect = (lastDisconnect.error instanceof Boom)
                ? lastDisconnect.error.output.statusCode !== DisconnectReason.loggedOut
                : true;
            console.log('Connection closed. Reconnecting:', shouldReconnect);
            if (shouldReconnect) connectToWhatsApp();
        } else if (connection === 'open') {
            isReady = true;
            qrData = null;
            console.log('WhatsApp client is ready!');
        }
    });
}

connectToWhatsApp();

app.get('/status', (req, res) => {
    res.json({ ready: isReady, qr: qrData });
});

app.post('/send', async (req, res) => {
    const { phone, message } = req.body;
    if (!isReady) return res.status(503).json({ error: 'WhatsApp not ready' });
    if (!phone || !message) return res.status(400).json({ error: 'phone and message required' });

    try {
        const jid = phone.replace('+', '').replace(/\s/g, '') + '@s.whatsapp.net';
        await sock.sendMessage(jid, { text: message });
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

const PORT = 3001;
app.listen(PORT, () => console.log(`WhatsApp bridge running on port ${PORT}`));
