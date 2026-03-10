from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime
import pytz
import requests
import uuid
import os

app = Flask(__name__)

WHATSAPP_BRIDGE = "http://localhost:3001"

jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///jobs.db')}
scheduler = BackgroundScheduler(jobstores=jobstores, job_defaults={'misfire_grace_time': 60}, timezone=pytz.utc)
scheduler.start()


def send_whatsapp_message(phone, message):
    try:
        res = requests.post(f"{WHATSAPP_BRIDGE}/send", json={"phone": phone, "message": message})
        print(f"[{datetime.now()}] Sent to {phone}: {res.json()}")
    except Exception as e:
        print(f"Error sending message: {e}")


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
    send_whatsapp_message(phone, message)
    return jsonify({"success": True})


@app.route('/api/send_bulk', methods=['POST'])
def send_bulk():
    data = request.json
    phones = data.get('phones', [])
    message = data.get('message')
    if not phones or not message:
        return jsonify({"error": "phones and message required"}), 400
    for phone in phones:
        send_whatsapp_message(phone, message)
    return jsonify({"success": True, "sent": len(phones)})


@app.route('/api/schedule', methods=['POST'])
def schedule_message():
    data = request.json
    phones = data.get('phones') or ([data.get('phone')] if data.get('phone') else [])
    message = data.get('message')
    send_at = data.get('send_at')
    repeat = data.get('repeat', 'none')  # none | daily | weekly | yearly

    if not phones or not message or not send_at:
        return jsonify({"error": "phones, message and send_at required"}), 400

    if len(send_at) == 16:
        send_at += ':00'

    run_date = datetime.fromisoformat(send_at).replace(tzinfo=pytz.utc)
    job_ids = []

    try:
        for phone in phones:
            job_id = str(uuid.uuid4())
            if repeat == 'daily':
                scheduler.add_job(
                    send_whatsapp_message, 'cron',
                    hour=run_date.hour, minute=run_date.minute,
                    args=[phone, message], id=job_id,
                    replace_existing=True
                )
            elif repeat == 'weekly':
                scheduler.add_job(
                    send_whatsapp_message, 'cron',
                    day_of_week=run_date.strftime('%a').lower(),
                    hour=run_date.hour, minute=run_date.minute,
                    args=[phone, message], id=job_id,
                    replace_existing=True
                )
            elif repeat == 'yearly':
                scheduler.add_job(
                    send_whatsapp_message, 'cron',
                    month=run_date.month, day=run_date.day,
                    hour=run_date.hour, minute=run_date.minute,
                    args=[phone, message], id=job_id,
                    replace_existing=True
                )
            else:
                scheduler.add_job(
                    send_whatsapp_message, 'date',
                    run_date=run_date,
                    args=[phone, message], id=job_id
                )
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
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time),
            "args": job.args,
            "repeat": repeat
        })
    return jsonify(jobs)


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    try:
        scheduler.remove_job(job_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
