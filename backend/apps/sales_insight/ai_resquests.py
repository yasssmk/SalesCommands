from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key = settings.OPENAI_API_KEY["OPENAI_API_KEY"])
model = "gpt-4o-mini"
temperature = 0.3

def call_llm(prompt, model=model, temperature=temperature):
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

    return completion.choices[0].message.content




