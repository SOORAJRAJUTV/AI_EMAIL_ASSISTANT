# src/web_search.py - Auto-generated file
import requests
from config import GOOGLE_SEARCH_API_KEY, GOOGLE_CX

def google_search(query):
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_SEARCH_API_KEY}&cx={GOOGLE_CX}"
    response = requests.get(url)
    results = response.json().get("items", [])
    return [item["snippet"] for item in results][:3]
