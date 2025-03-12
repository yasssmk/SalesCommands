#Activity Analisys

COMMON_INSTRUCTIONS = """
    You are an AI assistant that extracts sales qualification data from text and returns structured sales qualification insight in JSON format. 
    I will provide you with a sanitized transcript from email conversations, call notes, or a complete call transcript between a sales AE and interlocutors (prospect, client, or partner). 
    You will extract and summarize the relevant information and organize them in the following JSON structure. This data will be used by the sales team to spot opportunities, estimate potential, analyze whitespace, and make strategic decisions around accounts.
    
    Think of your output as an expanded version of MEDPICC, turned into JSON with clear, actionable insights. 
    We specifically categorize insights at different levels:
       1) Account level 
       2) Organizational units 
       3) Contacts
    Adhere strictly to the rules:
      1. If data is unclear or missing, use null/0/false/[] as appropriate. 
      2. Don’t invent data not explicitly stated or reasonably implied.
      3. Provide measurable objectives when possible.
      4. Focus on the data relevant for sales qualification: pains, goals, budgets, processes, etc.
      5. Return valid JSON matching the exact structures shown, with no extra commentary.
    
    Additional clarifications:
      - For **objectives**, make them measurable and actionable (e.g., “Increase sales by 20% within 6 months”).
      - For **motivations**, specify reasons driving interest (e.g., “Expand market share”).
      - For **implications**, quantify the impact (e.g., “Risk losing 10% of revenue”).
      - For **techStack** items, do not invent yearsOfUsage if not stated.
      - For **projects**, do not invent targetYear or usage durations. If not mentioned, leave it null/0.
      - Each level (Account, OrgUnit, Contact) can have relevant pains, processes, or budget data.
    
    Here is a comprehensive guide if applicable:
       1. Account Info + Insights
       2. Org Units Insights
       3. Contacts Insights
       4. Focus on key fields: objectives, painPoints, currentTechStack, buyingProcess, projects, etc.
"""

ACCOUNT_INSIGHTS_DEFINITIONS = """
    We have two main sections to fill in a single JSON:
      1) "accountInfo"
      2) "accountInsights"
    
    ACCOUNT INFO FIELDS:
      - accountName: Official company name.
      - accountType: e.g., CLIENT, PROSPECT, PARTNER.
      - classification: SMB, MIDMARKET, ENTERPRISE, etc.
      - employeeCount: Approx number of employees, if stated.
      - annualRevenue: Numeric revenue, if stated.
      - buyingDecisionsLocation: Where major decisions happen.
      - parentCompany: If a subsidiary, with "companyName", "accountId".
      - orgUnits: Array of org units (keep it empty for now).
    
    ACCOUNT INSIGHTS FIELDS:
      - objectives, compellingEvents, motivations, keyKPIs, criteria
      - painPoints, implications
      - currentTechStack (array of sub-objects)
      - partners: external vendors or consulting firms
      - budget, newBudgetStartDate
      - buyingProcess (array of sub-objects: stepName, department, stakeholderRole, influenceScore, stepGoals, expectedOutcomes, averageTimeInDays)
      - projects (array of sub-objects: projectName, targetYear, keyInitiatives, compellingEvents, products, metrics, painPoints, impacts, decisionCriteria, hasStarted, relevantDates, budgetAllocation, estimatedUnitsNeeded, unitOfMeasure, stakeholders)
    
    JSON STRUCTURE TO RETURN (for this prompt):

    {
    "accountInfo": {
        "accountName": "",
        "accountType": "",
        "classification": "",
        "employeeCount": 0,
        "annualRevenue": 0,
        "buyingDecisionsLocation": "",
        "parentCompany": {
        "companyName": "",
        "accountId": ""
        },
        "orgUnits": []
    },
    "insights": {
        "accountInsights": {
        "objectives": [],
        "compellingEvents": [],
        "motivations": [],
        "keyKPIs": [],
        "criteria": [],
        "painPoints": [],
        "implications": [],
        "currentTechStack": [
            {
            "techName": "",
            "businessGoal": "",
            "popularityScore": 0,
            "pros": "",
            "improvementPoints": "",
            "yearsOfUsage": "",
            "costs": [],
            "renewalDate": ""
            }
        ],
        "partners": [],
        "budget": 0,
        "newBudgetStartDate": "",
        "buyingProcess": [
            {
            "stepName": "",
            "department": "",
            "stakeholderRole": "",
            "influenceScore": 0,
            "stepGoals": [],
            "expectedOutcomes": [],
            "averageTimeInDays": 0
            }
        ],
        "projects": [
            {
            "projectName": "",
            "targetYear": 0,
            "keyInitiatives": [],
            "compellingEvents": [],
            "products": [],
            "metrics": [],
            "painPoints": [],
            "impacts": [],
            "decisionCriteria": [],
            "hasStarted": false,
            "relevantDates": {
                "startDate": "",
                "technicalValidation": "",
                "solutionValidation": "",
                "quoteValidation": "",
                "contractSignature": "",
                "implementation": "",
                "goLive": "",
                "otherDates": []
            },
            "budgetAllocation": 0,
            "estimatedUnitsNeeded": 0,
            "unitOfMeasure": "",
            "stakeholders": [
                {
                "name": "",
                "role": "",
                "influenceLevel": "",
                "rolesInProcess": [],
                "contactInfo": {
                    "email": "",
                    "phone": ""
                }
                }
            ]
            }
        ]
        }
    }
    }

"""
ORG_UNITS_DEFINITIONS = """
    Return ONLY "orgUnitsInsights" array in valid JSON.

    orgUnitsInsights fields:
      organizationName, unitType, objectives, compellingEvents, motivations,
      keyKPIs, criteria, painPoints, implications, currentTechStack, partners,
      budget, newBudgetStartDate, buyingProcess, projects

JSON STRUCTURE:

{
  "orgUnitsInsights": [
    {
      "organizationName": "",
      "unitType": "",
      "objectives": [],
      "compellingEvents": [],
      "motivations": [],
      "keyKPIs": [],
      "criteria": [],
      "painPoints": [],
      "implications": [],
      "currentTechStack": [
        {
          "techName": "",
          "businessGoal": "",
          "popularityScore": 0,
          "pros": "",
          "improvementPoints": "",
          "yearsOfUsage": "",
          "costs": [],
          "renewalDate": ""
        }
      ],
      "partners": [],
      "budget": 0,
      "newBudgetStartDate": "",
      "buyingProcess": [
        {
          "stepName": "",
          "department": "",
          "stakeholderRole": "",
          "influenceScore": 0,
          "stepGoals": [],
          "expectedOutcomes": [],
          "averageTimeInDays": 0
        }
      ],
      "projects": [
        {
          "projectName": "",
          "targetYear": 0,
          "keyInitiatives": [],
          "compellingEvents": [],
          "products": [],
          "metrics": [],
          "painPoints": [],
          "impacts": [],
          "decisionCriteria": [],
          "hasStarted": false,
          "relevantDates": {
            "startDate": "",
            "technicalValidation": "",
            "solutionValidation": "",
            "quoteValidation": "",
            "contractSignature": "",
            "implementation": "",
            "goLive": "",
            "otherDates": []
          },
          "budgetAllocation": 0,
          "estimatedUnitsNeeded": 0,
          "unitOfMeasure": "",
          "stakeholders": [
            {
              "name": "",
              "role": "",
              "influenceLevel": "",
              "rolesInProcess": [],
              "contactInfo": {
                "email": "",
                "phone": ""
              }
            }
          ]
        }
      ]
    }
  ]
}
"""

CONTACTS_DEFINITIONS = """
    Return ONLY "contactsInsights" array in valid JSON.

    contactsInsights fields:
      contactName, role, orgUnit, influenceLevel, contactRoles,
      objectives (array of {goal, metrics, timeline}),
      motivations, keyKPIs, criteria, painPoints, implications,
      currentTechStack, partners, hasBudgetAuthority,
      projectsInvolved (array of {projectName})

    SAMPLE JSON:

{
  "contactsInsights": [
    {
      "contactName": "",
      "role": "",
      "orgUnit": "",
      "influenceLevel": "",
      "contactRoles": [],
      "objectives": [
        {
          "goal": "",
          "metrics": "",
          "timeline": []
        }
      ],
      "motivations": [],
      "keyKPIs": [],
      "criteria": [],
      "painPoints": [],
      "implications": [],
      "currentTechStack": [
        {
          "techName": "",
          "businessGoal": "",
          "popularityScore": 0,
          "pros": "",
          "improvementPoints": "",
          "yearsOfUsage": "",
          "costs": [],
          "renewalDate": ""
        }
      ],
      "partners": [],
      "hasBudgetAuthority": false,
      "projectsInvolved": [
        {
          "projectName": ""
        }
      ]
    }
  ]
}
"""

FALLBACK_PROMPT_IF_ERROR = """\
You provided invalid or incomplete JSON. 
Please correct it so it is valid JSON with proper braces and no repeated or missing keys.

Original (malformed) JSON:
{malformed_json}

Return ONLY valid JSON. Do not add extra commentary.
"""

# =====================================
# PROMPT-BUILDING FUNCTIONS
# =====================================

def get_account_insights_prompt(transcript):
    """
    Builds a prompt for "accountInfo" + "accountInsights" using
    centralized definitions and instructions.
    """
    print(f"GET ACCOUNT METH: {COMMON_INSTRUCTIONS}")
    print(f"GET ACCOUNT METH: {ACCOUNT_INSIGHTS_DEFINITIONS}")
    print(f"GET ACCOUNT METH: {transcript}")
    return f"""{COMMON_INSTRUCTIONS}
{ACCOUNT_INSIGHTS_DEFINITIONS}

Now, return only the 'accountInfo' and 'accountInsights' sections in valid JSON.
TRANSCRIPT:
\"\"\"{transcript}\"\"\""""


def get_org_units_prompt(transcript):
    """
    Builds a prompt for "orgUnitsInsights" only, using centralized definitions.
    """
    return f"""{COMMON_INSTRUCTIONS}
        {ORG_UNITS_DEFINITIONS}
        Return only the 'orgUnitsInsights' array in valid JSON.
        TRANSCRIPT:
        \"\"\"{transcript}\"\"\""""


def get_contacts_prompt(transcript):
    """
    Builds a prompt for "contactsInsights" only, using centralized definitions.
    """
    return f"""{COMMON_INSTRUCTIONS}
        {CONTACTS_DEFINITIONS}
        Return only the 'contactsInsights' array in valid JSON.
        TRANSCRIPT:
        \"\"\"{transcript}\"\"\""""


# =====================================
# JSON PARSING + MERGING LOGIC
# =====================================


import json 
from apps.LLM_calls.services import LLMProviderService
llm_service = LLMProviderService()

system_message = "You are a helpful, structured data extraction assistant."

def parse_json_with_defaults(json_string):
    """
    Safely parse the JSON string and ensure 
    missing keys become null or empty (if needed).
    Here, we'll do minimal validation. 
    In a real scenario, you'd define a full schema check.
    """
    try:
        data = json.loads(json_string)
        return data
    except json.JSONDecodeError:
        # If the AI returns invalid JSON, you can fallback or re-prompt
        return None
    
def parse_and_fallback_if_needed(llm_response, prompt):
    """ 
    Try parsing LLM response, apply fallback if needed.
    """
    stripped_response = strip_backticks_and_code_fences(llm_response)
    data = parse_json_with_defaults(stripped_response)
    
    if data is None:
        fallback_prompt = FALLBACK_PROMPT_IF_ERROR.format(malformed_json=stripped_response)
        new_response = llm_service.call_llm(user_prompt=fallback_prompt, system_message=system_message )
        stripped_new_response = strip_backticks_and_code_fences(new_response)
        data = parse_json_with_defaults(stripped_new_response)

    return data

def strip_backticks_and_code_fences(llm_text: str) -> str:
    """
    Removes triple backticks or code fences from the model's response
    so that json.loads(...) won't fail.
    """
    # Quick approach: remove any leading/trailing ``` with optional `json`
    clean = llm_text.strip()
    clean = clean.replace("```json", "").replace("```", "")
    return clean.strip()

# from .ai_resquests import call_llm



def get_full_insights(transcript):
    """ Extracts all qualification data from a transcript """

    # 1) Extract Account Insights
    prompt_1 = get_account_insights_prompt(transcript)
    data_1 = parse_and_fallback_if_needed(llm_service.call_llm(user_prompt=prompt_1,system_message=system_message), prompt_1)

    # 2) Extract Org Units Insights
    prompt_2 = get_org_units_prompt(transcript)
    data_2 = parse_and_fallback_if_needed(llm_service.call_llm(user_prompt=prompt_2,system_message=system_message), prompt_2)

    # 3) Extract Contacts Insights
    prompt_3 = get_contacts_prompt(transcript)
    data_3 = parse_and_fallback_if_needed(llm_service.call_llm(user_prompt=prompt_3,system_message=system_message), prompt_3)

    # Base JSON structure
    final_structure = {
        "accountInfo": data_1.get("accountInfo", {}),
        "insights": {
            "accountInsights": data_1.get("accountInsights", {}),
            "orgUnitsInsights": data_2.get("orgUnitsInsights", []),
            "contactsInsights": data_3.get("contactsInsights", [])
        }
    }

    return final_structure