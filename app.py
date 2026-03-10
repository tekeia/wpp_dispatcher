from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime
import requests
import uuid
import os

app = Flask(__name__)

WHATSAPP_BRIDGE = "http://localhost:3001"

jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///jobs.db')}
scheduler = BackgroundScheduler(jobstores=jobstores)
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


@app.route('/api/schedule', methods=['POST'])
def schedule_message():
    data = request.json
    phone = data.get('phone')
    message = data.get('message')
    send_at = data.get('send_at')

    if not all([phone, message, send_at]):
        return jsonify({"error": "phone, message and send_at required"}), 400

    try:
        run_date = datetime.fromisoformat(send_at)
        job_id = str(uuid.uuid4())
        scheduler.add_job(
            send_whatsapp_message,
            'date',
            run_date=run_date,
            args=[phone, message],
            id=job_id
        )
        return jsonify({"success": True, "job_id": job_id, "scheduled_at": send_at})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/jobs')
def list_jobs():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time),
            "args": job.args
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
