import base64
import email
import os
import json
import logging
from email.utils import parseaddr
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv

# Initialize logging and environment
load_dotenv()
logger = logging.getLogger(__name__)

# Configuration constants
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
BOT_EMAIL = os.getenv("BOT_EMAIL")
MAX_EMAIL_SIZE = 10 * 1024 * 1024  # 10MB
REPLIED_EMAILS_FILE = "replied_emails.json"
MAX_RESULTS = 25  # Default number of emails to fetch

def load_replied_emails():
    """Load list of already replied emails from JSON file"""
    try:
        if os.path.exists(REPLIED_EMAILS_FILE):
            with open(REPLIED_EMAILS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading replied emails: {str(e)}")
        return []

def save_replied_email(email_id):
    """Save email ID to prevent duplicate replies"""
    try:
        replied_emails = load_replied_emails()
        if email_id not in replied_emails:
            replied_emails.append(email_id)
            with open(REPLIED_EMAILS_FILE, 'w') as f:
                json.dump(replied_emails, f)
    except Exception as e:
        logger.error(f"Error saving replied email: {str(e)}")

def authenticate_gmail():
    """Authenticate and return Gmail service with automatic token refresh"""
    try:
        creds = Credentials.from_authorized_user_info({
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": GMAIL_REFRESH_TOKEN,
            "token_uri": "https://oauth2.googleapis.com/token"
        })
        
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise

def fetch_emails(max_results=MAX_RESULTS):
    """
    Fetch recent unread emails from inbox
    Returns: List of email dictionaries with id, threadId, from, subject, date, snippet
    """
    try:
        service = authenticate_gmail()
        replied_emails = load_replied_emails()
        
        # Fetch email metadata
        result = service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q="is:inbox -from:me is:unread",
            labelIds=['INBOX']
        ).execute()
        
        messages = result.get('messages', [])
        emails = []
        
        for msg in messages:
            if msg['id'] in replied_emails:
                continue
                
            try:
                # Get message details
                msg_data = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                # Skip large emails
                if int(msg_data.get('sizeEstimate', 0)) > MAX_EMAIL_SIZE:
                    continue
                
                # Parse headers
                headers = {h['name'].lower(): h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
                
                emails.append({
                    'id': msg['id'],
                    'threadId': msg_data['threadId'],
                    'from': parseaddr(headers.get('from', ''))[1] or headers.get('from', ''),
                    'subject': headers.get('subject', 'No Subject'),
                    'date': headers.get('date', datetime.now().isoformat()),
                    'snippet': msg_data.get('snippet', '')
                })
                
            except Exception as e:
                logger.error(f"Error processing email {msg['id']}: {str(e)}")
                continue
                
        return emails

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        if error.resp.status == 429:
            raise Exception("Gmail API rate limit exceeded. Please try again later.")
        return []
    except Exception as e:
        logger.error(f"Error fetching emails: {str(e)}")
        return []

def get_email_details(email_id):
    """Get complete details of a specific email including body content"""
    try:
        service = authenticate_gmail()
        msg_data = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()
        
        # Process headers
        headers = {h['name'].lower(): h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
        
        email_details = {
            'id': email_id,
            'threadId': msg_data['threadId'],
            'from': parseaddr(headers.get('from', ''))[1] or headers.get('from', ''),
            'subject': headers.get('subject', 'No Subject'),
            'date': headers.get('date', datetime.now().isoformat()),
            'snippet': msg_data.get('snippet', ''),
            'body': ''
        }
        
        # Extract email body
        parts = msg_data.get('payload', {}).get('parts', [])
        for part in parts:
            if part['mimeType'] in ['text/plain', 'text/html']:
                try:
                    data = part['body'].get('data', '')
                    if data:
                        email_details['body'] = base64.urlsafe_b64decode(data + '===').decode('utf-8')
                        break
                except Exception as e:
                    logger.warning(f"Error decoding part {part['partId']}: {str(e)}")
                    continue
                    
        return email_details
        
    except HttpError as error:
        logger.error(f"Gmail API error getting email {email_id}: {error}")
        return None
    except Exception as e:
        logger.error(f"Error getting email details: {str(e)}")
        return None
    
def send_email_reply(to, subject, body, email_id, in_reply_to=None):
    """Send an email reply and track it in replied emails"""
    if not to:
        logger.error("No recipient specified for reply")
        return False

    try:
        service = authenticate_gmail()

        # Create email message
        msg = email.message.EmailMessage()
        msg.set_content(body)
        msg['To'] = to
        msg['Subject'] = subject
        msg['From'] = BOT_EMAIL

        if in_reply_to:
            msg['In-Reply-To'] = f"<{in_reply_to}>"
            msg['References'] = f"<{in_reply_to}>"

        # Encode and send
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()

        # Track successful reply
        save_replied_email(email_id)
        logger.info(f"Successfully sent reply to {to}")
        return True

    except HttpError as error:
        logger.error(f"Gmail API error sending reply: {error}")
        if error.resp.status == 429:
            logger.warning("Rate limit exceeded when sending email")
        return False
    except Exception as e:
        logger.error(f"Error sending email reply: {str(e)}")
        return False
