import os
from groq import Groq
from dotenv import load_dotenv
import json
from typing import Dict, Any

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def generate_reply(subject: str, context: str) -> str:
    """Generate a thoughtful email reply using LLM with improved context handling."""
    prompt = f"""
    You are an AI email assistant helping manage emails. Your task is to compose a professional reply.
    
    Context:
    - Email Subject: {subject}
    - Full Conversation Thread:
    {context}
    
    Instructions:
    1. Analyze the entire conversation thread
    2. Identify key questions/requests
    3. Draft a concise, polite response
    4. Maintain professional tone
    5. If scheduling is mentioned, propose specific times
    6. For questions, provide clear answers
    7. Keep under 200 words unless complex
    
    Format your response as plain text (no markdown).
    """
    
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating reply: {e}")
        return "I encountered an error generating a reply. Please try again later."


def calculate_priority_manually(email_text: str) -> int:
    """Basic keyword-based fallback priority logic."""
    email_text = email_text.lower()

    if "urgent" in email_text or "asap" in email_text or "immediately" in email_text:
        return 9
    elif "please respond" in email_text or "awaiting your response" in email_text:
        return 8
    elif "meeting" in email_text or "schedule" in email_text:
        return 7
    elif "reminder" in email_text:
        return 6
    elif "fyi" in email_text or "for your information" in email_text:
        return 3
    else:
        return 5


def analyze_email(email_text: str) -> Dict[str, Any]:
    """Analyze email content for priority, category, and action items."""
    prompt = f"""
    Analyze this email and return JSON with:
    - category (meeting, question, task, general)
    - priority (1-10)
    - requires_action (boolean)
    - action_type (reply, schedule, forward, none)
    - key_topics (array of strings)

    Email Content:
    {email_text}

    Return ONLY valid JSON:
    """
    
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        analysis = json.loads(response.choices[0].message.content)

        # Fallback priority logic if not present or too low/confusing
        model_priority = analysis.get("priority", 0)
        if model_priority < 1 or model_priority > 10:
            analysis["priority"] = calculate_priority_manually(email_text)

        return analysis

    except Exception as e:
        print(f"Error analyzing email: {e}")
        return {
            "category": "general",
            "priority": calculate_priority_manually(email_text),
            "requires_action": False,
            "action_type": "none",
            "key_topics": []
        }




