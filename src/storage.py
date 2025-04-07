import sqlite3
import os
from datetime import datetime

DB_FILE = "ai_email_assistant.db"

def init_db():
    """Initialize the database with required tables"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Create emails table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            sender TEXT,
            recipient TEXT,
            subject TEXT,
            timestamp TEXT,
            body TEXT,
            thread_id TEXT,
            is_reply INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create attachments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER,
            filename TEXT,
            file_path TEXT,
            FOREIGN KEY (email_id) REFERENCES emails (id)
        )
        ''')
        
        # Create actions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER,
            action_type TEXT,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (email_id) REFERENCES emails (id)
        )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deleted_emails (
                message_id TEXT PRIMARY KEY
            )
        ''')
        
        conn.commit()

def init_settings():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Initialize auto_reply_mode to OFF if not set
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('auto_reply_mode', 'off')
        ''')
        conn.commit()


def store_email(message_id, sender, recipient, subject, timestamp, body, thread_id=None, is_reply=False):
    """Store an email in the database"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO emails 
            (message_id, sender, recipient, subject, timestamp, body, thread_id, is_reply)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, sender, recipient, subject, timestamp, body, thread_id, int(is_reply)))
        conn.commit()



def get_emails(limit=10):
    """Fetch emails from database"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM emails 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_email_thread(thread_id):
    """Get all emails in a thread"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM emails 
            WHERE thread_id = ? 
            ORDER BY created_at ASC
        ''', (thread_id,))
        return [dict(row) for row in cursor.fetchall()]
    
def is_email_deleted(message_id):
    """Check if the email with given message_id has been marked as deleted"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM deleted_emails WHERE message_id = ?
        ''', (message_id,))
        result = cursor.fetchone()
        return result is not None
    
def mark_email_deleted(message_id):
    """Mark an email as deleted by adding it to the deleted_emails table"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO deleted_emails (message_id)
            VALUES (?)
        ''', (message_id,))
        conn.commit()




def log_action(email_id, action_type, details=None):
    """Log an action taken on an email"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO actions (email_id, action_type, details)
            VALUES (?, ?, ?)
        ''', (email_id, action_type, details))
        conn.commit()


def is_auto_reply_enabled():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'auto_reply_mode'")
        row = cursor.fetchone()
        return row and row[0] == 'on'

def set_auto_reply_mode(enabled):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        value = 'on' if enabled else 'off'
        cursor.execute('''
            UPDATE settings
            SET value = ?
            WHERE key = 'auto_reply_mode'
        ''', (value,))
        conn.commit()




# Initialize database when module is imported
init_db()
init_settings()



































# # src/storage.py - Auto-generated file
# import sqlite3

# # Database file
# DB_FILE = "ai_email_assistant.db"

# def create_tables():
#     """
#     Initializes the database with the necessary tables.
#     """
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()

#     # Table for storing emails
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS emails (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             message_id TEXT UNIQUE,
#             sender TEXT,
#             recipient TEXT,
#             subject TEXT,
#             timestamp TEXT,
#             body TEXT,
#             thread_id TEXT,
#             is_reply INTEGER DEFAULT 0
#         )
#     ''')

#     # Table for storing email attachments
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS attachments (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             email_id INTEGER,
#             filename TEXT,
#             file_path TEXT,
#             FOREIGN KEY (email_id) REFERENCES emails (id)
#         )
#     ''')

#     conn.commit()
#     conn.close()

# def store_email(message_id, sender, recipient, subject, timestamp, body, thread_id=None, is_reply=False):
#     """
#     Stores an email in the database.
#     """
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()

#     cursor.execute('''
#         INSERT OR IGNORE INTO emails (message_id, sender, recipient, subject, timestamp, body, thread_id, is_reply)
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#     ''', (message_id, sender, recipient, subject, timestamp, body, thread_id, int(is_reply)))

#     conn.commit()
#     conn.close()

# def get_emails(limit=10):
#     """
#     Fetches the most recent emails from the database.
#     """
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()

#     cursor.execute('''
#         SELECT id, sender, recipient, subject, timestamp, body, thread_id FROM emails
#         ORDER BY timestamp DESC
#         LIMIT ?
#     ''', (limit,))

#     emails = cursor.fetchall()
#     conn.close()
#     return emails

# def get_email_by_id(email_id):
#     """
#     Fetches a specific email by ID.
#     """
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()

#     cursor.execute('''
#         SELECT id, sender, recipient, subject, timestamp, body, thread_id FROM emails WHERE id = ?
#     ''', (email_id,))

#     email = cursor.fetchone()
#     conn.close()
#     return email

# def get_email_thread(thread_id):
#     """
#     Retrieves all emails in the same conversation thread.
#     """
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()

#     cursor.execute('''
#         SELECT id, sender, recipient, subject, timestamp, body FROM emails WHERE thread_id = ?
#         ORDER BY timestamp ASC
#     ''', (thread_id,))

#     emails = cursor.fetchall()
#     conn.close()
#     return emails

# if __name__ == "__main__":
#     # Initialize database tables
#     create_tables()
#     print("✅ Database initialized successfully!")
