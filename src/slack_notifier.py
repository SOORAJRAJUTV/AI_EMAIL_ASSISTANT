import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")

def send_slack_notification(message):
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL:
        print("Slack credentials not configured")
        return False
    
    try:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": SLACK_CHANNEL,
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

















# # src/slack_notifier.py - Auto-generated file
# import requests
# from config import SLACK_BOT_TOKEN, SLACK_CHANNEL

# def send_slack_notification(message):
#     url = "https://slack.com/api/chat.postMessage"
#     headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"}
#     payload = {"channel": SLACK_CHANNEL, "text": message}
#     requests.post(url, headers=headers, json=payload)
