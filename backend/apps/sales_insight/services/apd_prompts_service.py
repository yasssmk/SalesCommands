import json
from apps.LLM_calls.services import LLMProviderService
llm_service = LLMProviderService()

SECOND_CALL_COMMON_INSTRUCTIONS = """
    You are an AI assistant that provides a structured JSON covering:
      1) Account objectives vs. product benefits
      2) Pain points vs. product features/benefits
      3) Economic impact (budget & ROI considerations)

    We will provide:
      - A list of 'account objectives'
      - A list of 'pain points'
      - Product 'key benefits' or 'key features'
      - Any relevant cost/savings info if available (optional)

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
      },

      "economicImpact": {
        "currentPainCost": "",
        "timeOrMoneySaved": "",
        "unitsThatMatter": "",
        "existingSolutionCost": "",
        "estimatedAccountPotential": "",
        "additionalCosts": []
      }
    }

    ***RULES***
      1. If an objective has no relevant product benefit, leave 'matchingProductBenefit' empty.
      2. For each pain point, if no product feature/benefit applies, leave them empty.
      3. Do NOT invent data. If uncertain, keep it minimal or empty strings.
      4. 'economicImpact' is high-level. If the transcript does not mention costs, or potential value, set them as empty strings or empty arrays.
      5. Return ONLY valid JSON. No extra commentary.

    ***NOTE***
      - "objectives": for each account objective, match relevant product benefit(s) and outline 'whyItHelps' plus 'expectedOutcome'.
      - "painPointsAnalysis": how each pain is addressed by product features/benefits.
      - "economicImpact": an overview of costs, savings, the relevant unit (FTE, seats, etc.), existing solution cost, total potential, and any extra costs.
"""

def get_second_call_prompt(
    account_objectives,
    account_pain_points,
    product_benefits
):
    """
    Builds a prompt for the second LLM call, covering:
      - objectives alignment
      - pain points coverage
      - economic impact
    """
    # Convert lists to bullet-form for clarity
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

Now, return the final JSON with this structure:

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
  }},
  "economicImpact": {{
    "currentPainCost": "",
    "timeOrMoneySaved": "",
    "unitsThatMatter": "",
    "existingSolutionCost": "",
    "estimatedAccountPotential": "",
    "additionalCosts": []
  }}
}}

For each objective in 'objectives', fill the 4 fields. 
For each pain point, create an item in 'painsCoverage'. 
If a product feature/benefit fits, list it under matchingProductFeatures/Benefits, otherwise leave them empty.
In 'economicImpact', fill the fields if the transcript or data suggest them, or set them empty if not mentioned.
"""

def call_second_llm_for_alignment(
    account_objectives, 
    account_pain_points, 
    product_benefits
):
    prompt = get_second_call_prompt(
        account_objectives, 
        account_pain_points, 
        product_benefits
    )
    response_text = llm_service.call_llm(user_prompt=prompt)
    # Optionally parse or validate JSON here
    return response_text
