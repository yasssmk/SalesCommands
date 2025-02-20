from openai import OpenAI
from django.conf import settings

client = OpenAI()

def call_llm(prompt, model="gpt-3.5-turbo", temperature=0.0):
    """
    Helper function to call OpenAI ChatCompletion API 
    with the given 'prompt' string.
    """
    completion = client.chat.completions.create(
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
    return completion["choices"][0]["message"]["content"]




