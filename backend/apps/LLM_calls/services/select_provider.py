from django.conf import settings
import openai
from core.exceptions import StandardizedValidationError, StandardizedAuthenticationFailed
from core.error_messages import CoreErrorMessages

MODEL_SELECTED = "OpenAI"
DEFAULT_MODEL_NAME = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.0


def connect_openAI(api_key, model, temperature, system_message, user_prompt):
    """
    Connect to OpenAI ChatCompletion using the provided key, model, temperature,
    and two different roles: system + user.
    """
    try:
        if not api_key:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_CONFIG)
        # Set the API key for this request
        openai.api_key = api_key

        

        completion = openai.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=temperature
        )
        return completion.choices[0].message.content
    
    except Exception as e:
        raise StandardizedValidationError(CoreErrorMessages.SERVICE_UNAVAILABLE)


class LLMProviderService:
    """
    Main class that routes requests to the correct provider function 
    based on the MODEL_SELECTED variable.
    """

    def __init__(self):
        # If you have any initialization or config reading, do it here
        pass

    def call_llm(self, user_prompt, system_message="",
                 temperature=DEFAULT_TEMPERATURE, model=DEFAULT_MODEL_NAME):
        """
        Main entry point for calling the LLM.
        You can override default model, temperature, or system_message as needed.
        """
        # If you store the user's or tenant's API keys differently, retrieve them here
        # For the example, let's assume OpenAI key from settings:

        if MODEL_SELECTED == "OpenAI":
            api_key = settings.OPENAI_API_KEY["OPENAI_API_KEY"]
            return connect_openAI(api_key, model, temperature, system_message, user_prompt)
        else:
            raise NotImplementedError(f"Provider '{MODEL_SELECTED}' is not implemented.")