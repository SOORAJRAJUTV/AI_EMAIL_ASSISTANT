import os
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()  # ✅ Load .env at the top

# ✅ Load after dotenv
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

def send_slack_notification(message):
    if not SLACK_BOT_TOKEN or not CHANNEL_ID:
        print("Slack credentials not configured")
        return False
    
    print("Using SLACK_BOT_TOKEN:", SLACK_BOT_TOKEN)
    print("Using CHANNEL_ID:", CHANNEL_ID)

    try:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "channel": CHANNEL_ID,
            "text": message,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*New Email Notification*\n{message}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()
        if not data.get('ok'):
            print(f"Slack API error: {data.get('error', 'Unknown error')}")
            return False

        return True

    except Exception as e:
        print(f"Error sending Slack notification: {e}")
        return False


