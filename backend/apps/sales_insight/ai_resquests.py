import openai
from django.conf import settings


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

def call_llm(prompt, model="gpt-3.5-turbo", temperature=0.0):
    """
    Helper function to call OpenAI ChatCompletion API 
    with the given 'prompt' string.
    """
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful, structured data extraction assistant."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=temperature
    )
    return response["choices"][0]["message"]["content"]




