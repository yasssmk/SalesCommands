import json
from apps.LLM_calls.services import LLMProviderService
llm_service = LLMProviderService()

SECOND_CALL_COMMON_INSTRUCTIONS = """
    You are an AI assistant that provides a structured JSON covering:
      1) Account objectives vs. product benefits
      2) Pain points vs. product features/benefits
      3) Value section (economic impact, TCO arguments)

    We will provide:
      - A list of 'account objectives'
      - A list of 'pain points'
      - Product 'key benefits' or 'key features'
      - (Optional) cost/savings info
      - A JSON list of 'replaceable tech stack' items with approximate costs

    Your output must have the following exact JSON structure:

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
      "valueSection": {
        "costOfImplications": "",
        "statusQuoCost": "",
        "productBenefitImpact": [
          {
            "benefitName": "",
            "qualitativeBenefit": "",
            "estimatedTimeOrMoneySaved": ""
          }
        ],
        "tcoSummary": {
          "arguments": [
            {
              "argumentTitle": "",
              "argumentDescription": "",
              "formulaOrEstimation": "",
              "assumptions": []
            }
          ],
          "overallValueStatement": ""
        }
      }
    }

    ***RULES***
      1. If an objective has no relevant product benefit, leave 'matchingProductBenefit' empty.
      2. For each pain point, if no product feature/benefit applies, leave them empty.
      3. Do NOT invent data not in the transcript or additional info. If uncertain, keep it minimal or empty.
      4. Return ONLY valid JSON. No extra commentary or code fences.
      5. Use the 'replaceable tech stack' data to refine 'statusQuoCost' or to build TCO arguments in 'tcoSummary' if relevant.
      6. 'costOfImplications' is the cost or risk of leaving pains unresolved. 'statusQuoCost' is the approximate cost of the existing solution. 
      7. 'productBenefitImpact' arrays show key product benefits with a short or numeric savings statement. 
      8. Under 'tcoSummary.arguments', you can detail any formula or assumption referencing the cost of the replaceable tech.

"""


def get_second_call_prompt(
    account_objectives,
    account_pain_points,
    product_benefits,
    replaceable_tech_stack
):
    """
    Builds the prompt for the second LLM call, covering:
      - objectives alignment
      - pain points coverage
      - value (economic impact, TCO)
      Also includes a JSON list of replaceable tech stack items
      so LLM can reflect them in statusQuoCost or tcoSummary if needed.
    """

    # Convert lists to bullet-form for clarity
    objectives_text = "\n".join(f"- {obj}" for obj in account_objectives)
    pains_text = "\n".join(f"- {pain}" for pain in account_pain_points)
    benefits_text = "\n".join(f"- {b}" for b in product_benefits)

    # The replaceable tech stack might already be JSON. We can either flatten or print it as text.
    # Suppose each item is a dict with 'techName', 'approxCost' fields:
    stack_lines = []
    for item in replaceable_tech_stack:
        line = f"- {item.get('techName','Unknown')} (approx cost: {item.get('approxCost','unknown')})"
        stack_lines.append(line)
    replaceable_text = "\n".join(stack_lines)

    return f"""{SECOND_CALL_COMMON_INSTRUCTIONS}

ACCOUNT OBJECTIVES:
{objectives_text}

ACCOUNT PAIN POINTS:
{pains_text}

PRODUCT KEY BENEFITS/FEATURES:
{benefits_text}

REPLACEABLE TECH STACK (approx costs):
{replaceable_text}

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
  "valueSection": {{
    "costOfImplications": "",
    "statusQuoCost": "",
    "productBenefitImpact": [
      {{
        "benefitName": "",
        "qualitativeBenefit": "",
        "estimatedTimeOrMoneySaved": ""
      }}
    ],
    "tcoSummary": {{
      "arguments": [
        {{
          "argumentTitle": "",
          "argumentDescription": "",
          "formulaOrEstimation": "",
          "assumptions": []
        }}
      ],
      "overallValueStatement": ""
    }}
  }}
}}

For each objective in 'objectives', fill the 4 fields.
For each pain point, create an item in 'painsCoverage'.
In 'valueSection', incorporate any cost references from the replaceable tech stack into 'statusQuoCost' or your TCO arguments if relevant.
"""


def call_second_llm_for_alignment(
    account_objectives, 
    account_pain_points, 
    product_benefits,
    replaceable_tech_stack
):
    prompt = get_second_call_prompt(
        account_objectives, 
        account_pain_points, 
        product_benefits,
        replaceable_tech_stack
    )
    response_text = llm_service.call_llm(user_prompt=prompt)
    # Optionally parse or validate JSON here
    return response_text
