# main.py - Updated version
from src.email_service import fetch_emails, get_sender_email, send_email_reply
from src.ai_processing import analyze_email, generate_reply
from src.web_search import google_search
from src.slack_notifier import send_slack_notification
from src.calendar_service import add_event_to_calendar
import os

# Get bot's email from environment variable
BOT_EMAIL = os.getenv("BOT_EMAIL")

# Fetch emails and process them
emails = fetch_emails()

for email in emails:
    sender_email = get_sender_email(email["id"])

    # Ignore emails sent by the bot itself
    if not sender_email or sender_email == BOT_EMAIL:
        print(f"⚠️ Skipping email from self: {sender_email}")
        continue

    # Analyze email content
    analysis = analyze_email(email["body"])

    if "schedule" in analysis:
        print("📅 Scheduling an event...")
        add_event_to_calendar("Meeting", "2024-04-03T10:00:00", "2024-04-03T11:00:00")
    elif "search" in analysis:
        print("🔍 Performing Google search...")
        results = google_search(email["body"])
        print(f"Search Results: {results}")
    else:
        print("✉️ Generating automated reply...")
        reply = generate_reply(email["body"])
        
        # FIXED: Pass email["id"] to send_email_reply()
        send_email_reply(sender_email, "Re: Your Email", reply, email["id"])
        print(f"✅ Replied to {sender_email}")

    # Send Slack notification
    print("🔔 Sending Slack notification...")
    send_slack_notification(f"Processed an email from {sender_email}")

print("✅ Done processing all emails!")






