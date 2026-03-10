from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime
import sqlite3
import pytz
import requests
import uuid
import os

app = Flask(__name__)

WHATSAPP_BRIDGE = "http://localhost:3001"
DB_PATH = "messages.db"

jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///jobs.db')}
scheduler = BackgroundScheduler(jobstores=jobstores, job_defaults={'misfire_grace_time': 60}, timezone=pytz.utc)
scheduler.start()


# ── DB INIT ─────────────────────────────────────────────────
def init_log_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS message_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        phone     TEXT NOT NULL,
        message   TEXT NOT NULL,
        status    TEXT NOT NULL DEFAULT 'sent',
        source    TEXT NOT NULL DEFAULT 'manual',
        sent_at   TEXT NOT NULL,
        event_id  TEXT,
        tags      TEXT
    )""")
    # Migrate existing tables that may not have the new columns
    try: con.execute('ALTER TABLE message_log ADD COLUMN event_id TEXT')
    except: pass
    try: con.execute('ALTER TABLE message_log ADD COLUMN tags TEXT')
    except: pass
    con.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT NOT NULL,
        phone     TEXT NOT NULL UNIQUE,
        tags      TEXT NOT NULL DEFAULT ''
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS calendar_events (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        key       TEXT NOT NULL UNIQUE,
        name      TEXT NOT NULL,
        emoji     TEXT NOT NULL DEFAULT '📅'
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS disabled_holidays (
        key       TEXT PRIMARY KEY
    )""")
    con.commit()
    con.close()

def log_message(phone, message, status='sent', source='manual', event_id=None, tags=None):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO message_log (phone, message, status, source, sent_at, event_id, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (phone, message, status, source, datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S'), event_id, tags)
    )
    con.commit()
    con.close()

init_log_db()


# ── WHATSAPP SEND ────────────────────────────────────────────
def send_whatsapp_message(phone, message, source='scheduled', event_id=None, tags=None):
    try:
        res = requests.post(f"{WHATSAPP_BRIDGE}/send", json={"phone": phone, "message": message})
        data = res.json()
        status = 'sent' if data.get('success') else 'failed'
        print(f"[{datetime.now()}] Sent to {phone}: {data}")
    except Exception as e:
        status = 'failed'
        print(f"Error sending message to {phone}: {e}")
    log_message(phone, message, status=status, source=source, event_id=event_id, tags=tags)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def status():
    try:
        res = requests.get(f"{WHATSAPP_BRIDGE}/status", timeout=3)
        return jsonify(res.json())
    except:
        return jsonify({"ready": False, "qr": None, "error": "Bridge offline"})


@app.route('/api/send', methods=['POST'])
def send_now():
    data = request.json
    phone = data.get('phone')
    message = data.get('message')
    if not phone or not message:
        return jsonify({"error": "phone and message required"}), 400
    send_whatsapp_message(phone, message, source='manual')
    return jsonify({"success": True})


@app.route('/api/send_bulk', methods=['POST'])
def send_bulk():
    data = request.json
    phones = data.get('phones', [])
    message = data.get('message')
    tags = ','.join(data.get('tags', [])) if data.get('tags') else None
    if not phones or not message:
        return jsonify({"error": "phones and message required"}), 400
    event_id = str(uuid.uuid4())[:8].upper()  # short readable event ID
    for phone in phones:
        send_whatsapp_message(phone, message, source='broadcast', event_id=event_id, tags=tags)
    return jsonify({"success": True, "sent": len(phones), "event_id": event_id})


@app.route('/api/schedule', methods=['POST'])
def schedule_message():
    data = request.json
    phones = data.get('phones') or ([data.get('phone')] if data.get('phone') else [])
    message = data.get('message')
    send_at = data.get('send_at')
    repeat = data.get('repeat', 'none')

    if not phones or not message or not send_at:
        return jsonify({"error": "phones, message and send_at required"}), 400
    if len(send_at) == 16:
        send_at += ':00'

    run_date = datetime.fromisoformat(send_at).replace(tzinfo=pytz.utc)
    job_ids = []

    try:
        for phone in phones:
            job_id = str(uuid.uuid4())
            source = 'scheduled' if repeat == 'none' else f'recurring:{repeat}'
            if repeat == 'daily':
                scheduler.add_job(send_whatsapp_message, 'cron',
                    hour=run_date.hour, minute=run_date.minute,
                    args=[phone, message, source], id=job_id, replace_existing=True)
            elif repeat == 'weekly':
                scheduler.add_job(send_whatsapp_message, 'cron',
                    day_of_week=run_date.strftime('%a').lower(),
                    hour=run_date.hour, minute=run_date.minute,
                    args=[phone, message, source], id=job_id, replace_existing=True)
            elif repeat == 'yearly':
                scheduler.add_job(send_whatsapp_message, 'cron',
                    month=run_date.month, day=run_date.day,
                    hour=run_date.hour, minute=run_date.minute,
                    args=[phone, message, source], id=job_id, replace_existing=True)
            else:
                scheduler.add_job(send_whatsapp_message, 'date',
                    run_date=run_date, args=[phone, message, source], id=job_id)
            job_ids.append(job_id)

        return jsonify({"success": True, "job_ids": job_ids, "scheduled_at": send_at, "repeat": repeat})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/jobs')
def list_jobs():
    jobs = []
    for job in scheduler.get_jobs():
        trigger_type = type(job.trigger).__name__
        repeat = 'none'
        if trigger_type == 'CronTrigger':
            fields = {f.name: str(f) for f in job.trigger.fields}
            if fields.get('day_of_week') not in ('*', None) and str(fields.get('day_of_week')) != '*':
                repeat = 'weekly'
            elif fields.get('month') not in ('*', None) and str(fields.get('month')) != '*':
                repeat = 'yearly'
            else:
                repeat = 'daily'
        jobs.append({"id": job.id, "next_run": str(job.next_run_time), "args": job.args, "repeat": repeat})
    return jsonify(jobs)


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    try:
        scheduler.remove_job(job_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route('/api/jobs/<job_id>', methods=['PUT'])
def edit_job(job_id):
    data = request.json
    phone   = data.get('phone')
    message = data.get('message')
    send_at = data.get('send_at')
    repeat  = data.get('repeat', 'none')

    if not phone or not message or not send_at:
        return jsonify({"error": "phone, message and send_at required"}), 400
    if len(send_at) == 16:
        send_at += ':00'

    try:
        scheduler.remove_job(job_id)
    except:
        pass

    run_date = datetime.fromisoformat(send_at).replace(tzinfo=pytz.utc)
    source = 'scheduled' if repeat == 'none' else f'recurring:{repeat}'
    try:
        if repeat == 'daily':
            scheduler.add_job(send_whatsapp_message, 'cron',
                hour=run_date.hour, minute=run_date.minute,
                args=[phone, message, source], id=job_id, replace_existing=True)
        elif repeat == 'weekly':
            scheduler.add_job(send_whatsapp_message, 'cron',
                day_of_week=run_date.strftime('%a').lower(),
                hour=run_date.hour, minute=run_date.minute,
                args=[phone, message, source], id=job_id, replace_existing=True)
        elif repeat == 'yearly':
            scheduler.add_job(send_whatsapp_message, 'cron',
                month=run_date.month, day=run_date.day,
                hour=run_date.hour, minute=run_date.minute,
                args=[phone, message, source], id=job_id, replace_existing=True)
        else:
            scheduler.add_job(send_whatsapp_message, 'date',
                run_date=run_date, args=[phone, message, source], id=job_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── CALENDAR EVENTS ─────────────────────────────────────────
@app.route('/api/calendar/events', methods=['GET'])
def get_calendar_events():
    con = sqlite3.connect(DB_PATH)
    events = [{'id': r[0], 'key': r[1], 'name': r[2], 'emoji': r[3]}
              for r in con.execute('SELECT id, key, name, emoji FROM calendar_events').fetchall()]
    con.close()
    return jsonify(events)

@app.route('/api/calendar/events', methods=['POST'])
def add_calendar_event():
    data = request.json
    key, name, emoji = data.get('key'), data.get('name'), data.get('emoji', '📅')
    if not key or not name:
        return jsonify({'error': 'key and name required'}), 400
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute('INSERT INTO calendar_events (key, name, emoji) VALUES (?, ?, ?)', (key, name, emoji))
        con.commit()
        con.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Event already exists for that date'}), 409

@app.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
def delete_calendar_event(event_id):
    con = sqlite3.connect(DB_PATH)
    con.execute('DELETE FROM calendar_events WHERE id = ?', (event_id,))
    con.commit()
    con.close()
    return jsonify({'success': True})

@app.route('/api/calendar/holidays/disabled', methods=['GET'])
def get_disabled_holidays():
    con = sqlite3.connect(DB_PATH)
    keys = [r[0] for r in con.execute('SELECT key FROM disabled_holidays').fetchall()]
    con.close()
    return jsonify(keys)

@app.route('/api/calendar/holidays/disabled', methods=['POST'])
def set_disabled_holidays():
    keys = request.json.get('keys', [])
    con = sqlite3.connect(DB_PATH)
    con.execute('DELETE FROM disabled_holidays')
    for k in keys:
        con.execute('INSERT OR IGNORE INTO disabled_holidays (key) VALUES (?)', (k,))
    con.commit()
    con.close()
    return jsonify({'success': True})


@app.route('/api/logs')
def get_logs():
    limit  = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    search = request.args.get('search', '')
    source = request.args.get('source', '')

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    query  = "SELECT * FROM message_log WHERE 1=1"
    params = []
    if search:
        query += " AND (phone LIKE ? OR message LIKE ?)"
        params += [f'%{search}%', f'%{search}%']
    if source:
        query += " AND source = ?"
        params.append(source)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = con.execute(query, params).fetchall()
    total = con.execute("SELECT COUNT(*) FROM message_log").fetchone()[0]
    con.close()

    return jsonify({"logs": [dict(r) for r in rows], "total": total})


@app.route('/api/logs', methods=['DELETE'])
def clear_logs():
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM message_log")
    con.commit()
    con.close()
    return jsonify({"success": True})


# ── CONTACTS API ────────────────────────────────────────────
@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM contacts ORDER BY name ASC").fetchall()
    con.close()
    return jsonify([{
        "id": r["id"], "name": r["name"], "phone": r["phone"],
        "tags": [t for t in r["tags"].split(",") if t]
    } for r in rows])


@app.route('/api/contacts', methods=['POST'])
def add_contact():
    data = request.json
    name  = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    tags  = ','.join([t.strip().lower() for t in data.get('tags', []) if t.strip()])
    if not name or not phone:
        return jsonify({"error": "name and phone required"}), 400
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO contacts (name, phone, tags) VALUES (?, ?, ?)", (name, phone, tags))
        con.commit()
        row = con.execute("SELECT * FROM contacts WHERE phone=?", (phone,)).fetchone()
        con.close()
        return jsonify({"success": True, "id": row[0]})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Phone number already exists"}), 409


@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
    con.commit()
    con.close()
    return jsonify({"success": True})


@app.route('/api/contacts/<int:contact_id>/tags', methods=['PUT'])
def update_tags(contact_id):
    data = request.json
    tags = ','.join([t.strip().lower() for t in data.get('tags', []) if t.strip()])
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE contacts SET tags=? WHERE id=?", (tags, contact_id))
    con.commit()
    con.close()
    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
