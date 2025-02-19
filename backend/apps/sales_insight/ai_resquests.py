import os
import django
import openai
from django.conf import settings

# Manually set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salescommands.settings")

# Initialize Django
django.setup()

def connect_to_llm_via_env():
    """
    Method 1: Connect to OpenAI (or another LLM service) 
    reading credentials from environment variables.
    """
    api_key = settings.OPEN_AI_KEY["OPEN_AI_KEY"]
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables.")
    
    openai.api_key = api_key
    
    return api_key

# Test connection
connect_to_llm_via_env()
