import json 
from apps.LLM_calls.services import LLMProviderService
llm_service = LLMProviderService()

# second_llm_prompt_service.py

SECOND_CALL_COMMON_INSTRUCTIONS = """
    You are an AI assistant that aligns the account's objectives with a product's key benefits or features. 
    I will provide:
      1) A set of account objectives (from the first LLM call).
      2) The product's key benefits or features.

    Your job is to produce a structured JSON showing how each objective can be addressed by the product's benefits, 
    including a brief explanation of why it helps, and an expected outcome or potential KPI impact.

    ***RULES***
      1. If an objective has no relevant matching product benefit, leave 'matchingProductBenefit' as an empty array.
      2. Do NOT invent data not implied by the text. If uncertain, keep it minimal or empty.
      3. Provide realistic, concise bullet points for 'whyItHelps' and 'expectedOutcome'.
      4. Return ONLY valid JSON. No extra commentary, code fences, or text.
      5. The exact JSON structure must match:

      {
        "objectives": [
          {
            "objectiveStatement": "",
            "matchingProductBenefit": [],
            "whyItHelps": [],
            "expectedOutcome": []
          }
        ]
      }

    ***NOTE***:
      - "matchingProductBenefit" refers to the product's 'key_benefits' or 'key_features' if they directly address that objective.
      - "whyItHelps" is a short explanation bullet list.
      - "expectedOutcome" is how the client’s objective may be fulfilled or improved by using those benefits.
"""

def get_objective_alignment_prompt(account_objectives, product_benefits):
    """
    Builds a prompt to align the account's objectives with the product's benefits.
    Arguments:
      account_objectives: list of strings from the first LLM call
      product_benefits: list of strings or short bullet points from the Product model
    """
    # Convert lists to bullet-form or to any format you prefer for clarity
    objectives_text = "\n".join(f"- {obj}" for obj in account_objectives)
    benefits_text = "\n".join(f"- {benefit}" for benefit in product_benefits)

    return f"""{SECOND_CALL_COMMON_INSTRUCTIONS}

Account Objectives:
{objectives_text}

Product Key Benefits/Features:
{benefits_text}

Now, return the final JSON with structure:
{{
  "objectives": [
    {{
      "objectiveStatement": "",
      "matchingProductBenefit": [],
      "whyItHelps": [],
      "expectedOutcome": []
    }}
  ]
}}

Provide one array item per account objective. If a product benefit clearly fits that objective, place it in 'matchingProductBenefit'. Otherwise, leave it empty.
"""

def call_second_llm_for_objectives(account_objectives, product_benefits, llm_service):
    prompt = get_objective_alignment_prompt(account_objectives, product_benefits)
    response_text = llm_service.call_llm(user_prompt=prompt)
    # You’d parse or validate the JSON here similarly to parse_and_fallback_if_needed
    return response_text
