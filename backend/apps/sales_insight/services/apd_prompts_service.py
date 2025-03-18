# # second_llm_prompt_service.py

import json
from apps.LLM_calls.services import LLMProviderService
llm_service = LLMProviderService()

SECOND_CALL_COMMON_INSTRUCTIONS = """
    You are an AI assistant that provides a structured JSON aligning:
      1) Account objectives with product benefits
      2) Pain points with product features/benefits

    We will provide:
      - A list of 'account objectives' (from the first LLM call)
      - A list of 'pain points' discovered
      - A list of 'product key benefits' or 'product features'

    Your output must have the following JSON structure:

    {
      "objectives": [
        {
          "objectiveStatement": "",
          "matchingProductBenefit": [],
          "whyItHelps": [],
          "expectedOutcome": []
        }
      ],
      "painPointsAnalysis": {
        "painsCoverage": [
          {
            "painPoint": "",
            "matchingProductFeatures": [],
            "matchingProductBenefits": [],
            "whyItHelps": []
          }
        ]
      }
    }

    ***RULES***
    1. If an objective has no relevant matching product benefit, leave 'matchingProductBenefit' empty.
    2. For each pain point, list which product features/benefits address it. If none applies, leave them empty.
    3. Do NOT invent data not implied by the text. If uncertain, keep it minimal or empty.
    4. Provide concise bullet points for 'whyItHelps' and 'expectedOutcome'.
    5. Return ONLY valid JSON with no extra commentary or code fences.

    ***NOTE***
    - "matchingProductBenefit" under objectives ties to product 'key_benefits' or 'key_features' if they support that objective.
    - "painPointsAnalysis.painsCoverage": For each pain, fill 'matchingProductFeatures' or 'matchingProductBenefits' as relevant.
    - "whyItHelps" is a brief explanation of how those benefits/features solve the problem or reach the goal.
    - "expectedOutcome" is how the client’s objective may be fulfilled/improved. (Only in the objectives section)
"""

def get_second_call_prompt(
    account_objectives,    # list of objective strings
    account_pain_points,   # list of pain point strings
    product_benefits       # list of benefits/features (strings)
):
    """
    Builds a prompt for the second LLM call, combining both:
     - objectives → product benefits alignment
     - pain points → product features/benefits alignment
    """
    # Convert lists into bullet-form for clarity in the prompt
    objectives_text = "\n".join(f"- {obj}" for obj in account_objectives)
    pains_text = "\n".join(f"- {pain}" for pain in account_pain_points)
    benefits_text = "\n".join(f"- {b}" for b in product_benefits)

    return f"""{SECOND_CALL_COMMON_INSTRUCTIONS}

ACCOUNT OBJECTIVES:
{objectives_text}

ACCOUNT PAIN POINTS:
{pains_text}

PRODUCT KEY BENEFITS/FEATURES:
{benefits_text}

Now, return the JSON in this exact shape:

{{
  "objectives": [
    {{
      "objectiveStatement": "",
      "matchingProductBenefit": [],
      "whyItHelps": [],
      "expectedOutcome": []
    }}
  ],
  "painPointsAnalysis": {{
    "painsCoverage": [
      {{
        "painPoint": "",
        "matchingProductFeatures": [],
        "matchingProductBenefits": [],
        "whyItHelps": []
      }}
    ]
  }}
}}

For each objective in 'objectives', fill the 4 fields. For each pain point, create an entry in painsCoverage. If a product benefit/feature clearly applies, list it; otherwise leave them empty.
"""

def call_second_llm_for_alignment(
    account_objectives, 
    account_pain_points, 
    product_benefits
):
    """
    Calls the LLM using the prompt built above, returning the raw JSON string.
    (You can parse it afterwards with your parse_and_fallback_if_needed if desired.)
    """
    prompt = get_second_call_prompt(
        account_objectives, 
        account_pain_points, 
        product_benefits
    )
    response_text = llm_service.call_llm(user_prompt=prompt)
    # Optionally parse or validate the JSON here
    return response_text
