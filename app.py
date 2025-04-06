from flask import Flask, render_template, request, jsonify, send_from_directory
from src.email_service import fetch_emails, get_sender_email, send_email_reply, get_email_details
from src.ai_processing import generate_reply, analyze_email
from src.slack_notifier import send_slack_notification
from src.storage import store_email, get_email_thread, init_db, log_action
from datetime import datetime
import os
import logging
import sqlite3
import time
import json
from functools import wraps
import warnings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable Google API cache warnings
warnings.filterwarnings("ignore", "file_cache is only supported")

# Custom memory cache for Google API
class MemoryCache:
    _CACHE = {}

    def get(self, url):
        return MemoryCache._CACHE.get(url)

    def set(self, url, content):
        MemoryCache._CACHE[url] = content

# Configure Google API cache
import googleapiclient.discovery
googleapiclient.discovery.cache = MemoryCache()

# Initialize Flask app
app = Flask(__name__, static_folder='static')

# Rate limiting variables
last_email_fetch = 0
EMAIL_FETCH_COOLDOWN = 60  # seconds

# Database initialization
init_db()

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
    """Fetch stored emails from the SQLite database."""
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
            emails.append({
                'id': row['message_id'],
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
            logger.warning("No emails found in Gmail")
            return jsonify({'success': False, 'error': 'No emails found'}), 404

        stored_count = 0
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
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing email {email.get('id')}: {str(e)}")

        db_emails = get_emails_from_db()
        return jsonify({
            'success': True,
            'count': len(db_emails),
            'emails': db_emails
        })

    except Exception as e:
        logger.error(f"Error in get_emails: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/emails/<email_id>')
def get_email(email_id):
    try:
        logger.info(f"Fetching details for email {email_id}")
        email_details = get_email_details(email_id)

        if not email_details:
            return jsonify({'success': False, 'error': 'Email not found'}), 404

        return jsonify({'success': True, 'email': email_details})

    except Exception as e:
        logger.error(f"Error getting email {email_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reply/generate', methods=['POST'])
def generate_reply_combined():
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 415

        data = request.get_json()
        email_id = data.get('email_id')

        if not email_id:
            return jsonify({'success': False, 'error': 'Email ID required'}), 400

        logger.info(f"Generating reply for email {email_id}")
        email_details = get_email_details(email_id)

        if not email_details:
            return jsonify({'success': False, 'error': 'Email not found'}), 404

        thread_emails = get_email_thread(email_details['threadId'])
        context = "\n\n".join([
            f"From: {e['sender']}\nSubject: {e['subject']}\n{e['body']}"
            for e in thread_emails
        ])

        reply = generate_reply(email_details['subject'], context)
        analysis = analyze_email(email_details['body'])

        log_action(
            email_id=email_id,
            action_type='reply_generated',
            details=json.dumps({
                'model': 'llama3-8b-8192',
                'context_length': len(context)
            })
        )

        if analysis.get('priority', 0) > 7:
            slack_msg = f"Important email from {email_details['from']}: {email_details['subject']}"
            send_slack_notification(slack_msg)
            log_action(
                email_id=email_id,
                action_type='slack_notification',
                details=slack_msg
            )

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
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reply/send', methods=['POST'])
def send_reply():
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 415

        data = request.get_json()
        required_fields = ['email_id', 'to', 'subject', 'body']

        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        logger.info(f"Sending reply for email {data['email_id']}")
        success = send_email_reply(
            to=data['to'],
            subject=data['subject'],
            body=data['body'],
            email_id=data['email_id']
        )

        if success:
            log_action(
                email_id=data['email_id'],
                action_type='reply_sent',
                details=json.dumps({
                    'to': data['to'],
                    'subject': data['subject'],
                    'body_length': len(data['body'])
                })
            )
            return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Failed to send email'}), 500

    except Exception as e:
        logger.error(f"Error sending reply: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/actions/<email_id>')
def get_actions(email_id):
    try:
        with sqlite3.connect("ai_email_assistant.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM actions 
                WHERE email_id = ?
                ORDER BY created_at DESC
            ''', (email_id,))
            actions = [dict(row) for row in cursor.fetchall()]
        return jsonify({'success': True, 'actions': actions})

    except Exception as e:
        logger.error(f"Error getting actions for email {email_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

if __name__ == '__main__':
    if not os.path.exists("ai_email_assistant.db"):
        logger.info("Database not found, initializing...")
        init_db()

    app.run(host='0.0.0.0', port=5000, debug=True)
