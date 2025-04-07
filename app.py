from flask import Flask, render_template, request, jsonify, send_from_directory
from src.email_service import fetch_emails, send_email_reply, get_email_details
from src.ai_processing import generate_reply, analyze_email
from src.slack_notifier import send_slack_notification
from src.storage import (
    store_email, get_email_thread, init_db, log_action,
    is_email_deleted, mark_email_deleted,
    is_auto_reply_enabled, set_auto_reply_mode
)

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os
import logging
import sqlite3
import time
import json
from functools import wraps
import warnings

# Disable Google API caching
class MemoryCache:
    _CACHE = {}
    def get(self, url): return MemoryCache._CACHE.get(url)
    def set(self, url, content): MemoryCache._CACHE[url] = content

import googleapiclient.discovery
googleapiclient.discovery.cache = MemoryCache()

app = Flask(__name__, static_folder='static')

notified_emails = set()
last_email_fetch = 0
EMAIL_FETCH_COOLDOWN = 60

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", "file_cache is only supported")

init_db()

# ---------------------------- Utilities ----------------------------
def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global last_email_fetch
        current_time = time.time()
        if current_time - last_email_fetch < EMAIL_FETCH_COOLDOWN:
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded',
                'retry_after': EMAIL_FETCH_COOLDOWN - (current_time - last_email_fetch)
            }), 429
        last_email_fetch = current_time
        return f(*args, **kwargs)
    return decorated_function

def get_emails_from_db(limit=100):
    try:
        with sqlite3.connect("ai_email_assistant.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT message_id, sender, recipient, subject, timestamp, body, thread_id 
                FROM emails 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()

        emails = []
        for row in rows:
            message_id = row['message_id']
            if is_email_deleted(message_id):
                continue
            emails.append({
                'id': message_id,
                'from': row['sender'],
                'to': row['recipient'],
                'subject': row['subject'],
                'date': row['timestamp'],
                'snippet': row['body'],
                'threadId': row['thread_id']
            })
        return emails
    except Exception as e:
        logger.error(f"Failed to fetch emails from DB: {str(e)}")
        return []

def json_error_response(message, code=400):
    return jsonify({'success': False, 'error': message}), code

# ---------------------------- Routes ----------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/health')
def health_check():
    db_exists = os.path.exists("ai_email_assistant.db")
    return jsonify({
        'status': 'healthy',
        'database': db_exists,
        'gmail_connected': bool(os.getenv("GMAIL_CLIENT_ID")),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/emails', methods=['GET'])
@rate_limit
def get_emails():
    try:
        logger.info("Fetching emails from Gmail API")
        gmail_emails = fetch_emails()

        if not gmail_emails:
            return jsonify({'success': False, 'error': 'No emails found'}), 404

        for email in gmail_emails:
            try:
                store_email(
                    message_id=email['id'],
                    sender=email['from'],
                    recipient='me',
                    subject=email.get('subject', 'No Subject'),
                    timestamp=email.get('date', datetime.now().isoformat()),
                    body=email.get('snippet', ''),
                    thread_id=email['threadId']
                )
            except Exception as e:
                logger.error(f"Error storing email {email.get('id')}: {str(e)}")

        db_emails = get_emails_from_db()
        return jsonify({'success': True, 'count': len(db_emails), 'emails': db_emails})

    except Exception as e:
        logger.error(f"Error in get_emails: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emails/<email_id>')
def get_email(email_id):
    try:
        if is_email_deleted(email_id):
            return jsonify({'success': False, 'error': 'Email not found (deleted)'}), 404

        email_details = get_email_details(email_id)
        if not email_details:
            return jsonify({'success': False, 'error': 'Email not found'}), 404

        return jsonify({'success': True, 'email': email_details})
    except Exception as e:
        logger.error(f"Error getting email {email_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emails/<email_id>/delete', methods=['POST'])
def delete_email(email_id):
    try:
        mark_email_deleted(email_id)
        log_action(email_id, 'deleted', 'Email marked as deleted')
        return jsonify({'success': True, 'message': 'Email marked as deleted'})
    except Exception as e:
        logger.error(f"Error deleting email {email_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reply/generate', methods=['POST'])
def generate_reply_combined():
    try:
        data = request.get_json()
        email_id = data.get('email_id')
        if not email_id:
            return json_error_response('Email ID required')

        if is_email_deleted(email_id):
            return json_error_response('Email is deleted', 404)

        email_details = get_email_details(email_id)
        if not email_details:
            return json_error_response('Email not found', 404)

        thread_emails = get_email_thread(email_details['threadId'])
        context = "\n\n".join([f"From: {e['sender']}\nSubject: {e['subject']}\n{e['body']}" for e in thread_emails])

        reply = generate_reply(email_details['subject'], context)
        analysis = analyze_email(email_details['body'])

        log_action(email_id, 'reply_generated', json.dumps({'model': 'llama3-8b-8192', 'context_length': len(context)}))

        if analysis.get('priority', 0) > 7:
            slack_msg = f"Important email from {email_details['from']}: {email_details['subject']}"
            send_slack_notification(slack_msg)
            log_action(email_id, 'slack_notification', slack_msg)

        return jsonify({
            'success': True,
            'reply': reply,
            'analysis': analysis,
            'sender': email_details['from'],
            'subject': email_details['subject'],
            'thread_count': len(thread_emails)
        })

    except Exception as e:
        logger.error(f"Error generating reply: {str(e)}")
        return json_error_response(str(e), 500)

@app.route('/api/reply/send', methods=['POST'])
def send_reply():
    try:
        data = request.get_json()
        required = ['email_id', 'to', 'subject', 'body']
        if not all(k in data for k in required):
            return json_error_response('Missing required fields')

        success = send_email_reply(
            to=data['to'],
            subject=data['subject'],
            body=data['body'],
            email_id=data['email_id'],
            in_reply_to=data['email_id']
        )

        if success:
            log_action(data['email_id'], 'reply_sent', json.dumps({
                'to': data['to'],
                'subject': data['subject'],
                'body_length': len(data['body'])
            }))
            return jsonify({'success': True})

        return json_error_response('Failed to send email', 500)
    except Exception as e:
        logger.exception("Error sending reply")
        return json_error_response(str(e), 500)


@app.route('/api/actions/<email_id>')
def get_actions(email_id):
    try:
        with sqlite3.connect("ai_email_assistant.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM actions WHERE email_id = ? ORDER BY created_at DESC', (email_id,))
            actions = [dict(row) for row in cursor.fetchall()]
        return jsonify({'success': True, 'actions': actions})
    except Exception as e:
        logger.error(f"Error getting actions for email {email_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/auto-reply/status", methods=["GET"])
def get_auto_reply_status():
    return jsonify({"auto_reply_enabled": is_auto_reply_enabled()}), 200

@app.route("/auto-reply/toggle", methods=["POST"])
def toggle_auto_reply():
    data = request.get_json()
    enabled = data.get("enabled", False)
    set_auto_reply_mode(enabled)
    return jsonify({"message": f"Auto reply mode set to {'on' if enabled else 'off'}."}), 200

@app.errorhandler(404)
def handle_404(e):
    return json_error_response('Endpoint not found', 404)

# ---------------------------- Scheduler ----------------------------
def scheduled_email_fetch():
    with app.app_context():
        global notified_emails
        try:
            logger.info("⏰ Scheduled: Checking for new emails...")
            gmail_emails = fetch_emails()
            gmail_ids = set(email['id'] for email in gmail_emails)

            with sqlite3.connect("ai_email_assistant.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT message_id FROM emails")
                local_ids = set(row[0] for row in cursor.fetchall())

            deleted_ids = local_ids - gmail_ids
            for msg_id in deleted_ids:
                cursor.execute("DELETE FROM emails WHERE message_id = ?", (msg_id,))
                logger.info(f"🗑️ Deleted stale email from DB: {msg_id}")
                if msg_id in notified_emails:
                    notified_emails.remove(msg_id)
            conn.commit()

            for email in gmail_emails:
                email_id = email['id']
                store_email(
                    message_id=email_id,
                    sender=email['from'],
                    recipient='me',
                    subject=email.get('subject', 'No Subject'),
                    timestamp=email.get('date', datetime.now().isoformat()),
                    body=email.get('snippet', ''),
                    thread_id=email['threadId']
                )
                analysis = analyze_email(email.get('snippet', ''))
                priority = analysis.get('priority', 0)

                if priority > 7 and email_id not in notified_emails:
                    slack_msg = f"📬 High Priority Email from {email['from']}: {email.get('subject', '')}"
                    send_slack_notification(slack_msg)
                    log_action(email_id, 'slack_notification', slack_msg)
                    notified_emails.add(email_id)

                if is_auto_reply_enabled():
                    reply_body = (
                        f"Hello,\n\n"
                        f"Thank you for your message. I'm currently unavailable but will get back to you as soon as possible.\n\n"
                        f"Best regards,\nAI Email Assistant"
                    )

                    send_email_reply(
                        to=email['from'],
                        subject=f"Re: {email.get('subject', 'No Subject')}",
                        body=reply_body,
                        email_id=email_id,
                        in_reply_to=email_id,
                    )
                    log_action(email_id, "auto-reply", "Auto reply sent")

            logger.info("✅ Scheduled email fetch complete.")
        except Exception as e:
            logger.error(f"❌ Scheduled fetch failed: {e}")

# ---------------------------- Run App ----------------------------
if __name__ == '__main__':
    if not os.path.exists("ai_email_assistant.db"):
        logger.info("Database not found, initializing...")
        init_db()

    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_email_fetch, 'interval', seconds=60)
    scheduler.start()

    app.run(host='0.0.0.0', port=5000, debug=True)
