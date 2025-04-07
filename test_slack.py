from src.slack_notifier import send_slack_notification
import os

print("SLACK_BOT_TOKEN:", os.getenv("SLACK_BOT_TOKEN"))  # Debug
print("CHANNEL_ID:", os.getenv("CHANNEL_ID"))            # Debug

message = "🛎️ Test notification from Python Slack bot!"

success = send_slack_notification(message)
if success:
    print("✅ Slack notification sent successfully!")
else:
    print("❌ Failed to send Slack notification.")
