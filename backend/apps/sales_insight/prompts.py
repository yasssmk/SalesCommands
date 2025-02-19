#Activity Analisys

# =====================================
# CENTRALIZED DEFINITIONS & INSTRUCTIONS
# =====================================
COMMON_INSTRUCTIONS = """
    You are an AI assistant that extracts structured sales insights from text. 
    I will provide you with a sanitized transcript from email conversation, call notes or a complete call transcript. 
    Produce JSON **only** for the "accountInfo" and "accountInsights" sections, 
    following these rules:

    1. If data for a field is not found, fill it with null, 0, false, or an empty array ([]) as appropriate.
    2. Use arrays or objects exactly as shown in the structure.
    3. Do not add extra keys. 
    4. Output must be valid JSON with correct nesting.
"""

ACCOUNT_INSIGHTS_DEFINITIONS = """
    We have two sections to fill in a single JSON object:
    1) "accountInfo"
    2) "accountInsights"

    Short definitions of each field:
    ACCOUNT INFO FIELDS:
    - accountName: The company's official or recognized name.
    - accountType: e.g. CLIENT, PROSPECT, PARTNER.
    - classification: Segment or size category (e.g. SMB, MIDMARKET, ENTERPRISE).
    - employeeCount: Approximate number of employees in the entire company.
    - annualRevenue: Approximate annual revenue as a numeric value.
    - buyingDecisionsLocation: Where or by whom major purchasing decisions are made.
    - parentCompany: If this company is a subsidiary (with "companyName" & "accountId").
    - orgUnits: Array of organizational units (we will fill them in another step, so leave it empty or default).

    ACCOUNT INSIGHTS FIELDS:
    - objectives: Major business goals or outcomes the company wants.
    - compellingEvents: Time-sensitive events or triggers that influence decisions.
    - motivations: Reasons driving their interest in new solutions.
    - keyKPIs: Key performance indicators they care about.
    - criteria: High-level conditions or requirements to select a product/solution.
    - painPoints: Main problems or obstacles the entire account faces.
    - implications: Consequences if those pain points are not resolved.
    - currentTechStack: Tools or technologies they currently use (with sub-fields):
    - techName, businessGoal, popularityScore (0-10), pros, improvementPoints, yearsOfUsage, costs, renewalDate.
    - partners: Other external vendors or consulting firms they work with.
    - budget: Estimated total budget for new initiatives.
    - newBudgetStartDate: When a new budget cycle or pool of funds becomes available.
    - buyingProcess: Steps or phases the account goes through to evaluate and purchase solutions (with sub-fields):
    - stepName, department, stakeholderRole, influenceScore (0-10), stepGoals, expectedOutcomes, averageTimeInDays.
    - projects: Upcoming or ongoing initiatives relevant to the entire account (with sub-fields):
    - projectName, targetYear, keyInitiatives, compellingEvents, products, metrics, painPoints, impacts,
        decisionCriteria, hasStarted (bool), relevantDates (milestones), budgetAllocation, estimatedUnitsNeeded,
        unitOfMeasure, and stakeholders who are involved.

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
We want ONLY the "orgUnitsInsights" array in valid JSON format.

orgUnitsInsights fields:
- organizationName: e.g. “Engineering Dept”.
- unitType: e.g. DEPARTMENT, DIVISION, TEAM.
- objectives: Key goals for this unit.
- compellingEvents: Time-based triggers for this unit's decisions.
- motivations: Specific drivers within this unit.
- keyKPIs: The KPIs they track.
- criteria: Requirements for solutions or changes.
- painPoints: Challenges or issues the unit faces.
- implications: Consequences if those issues aren’t solved.
- currentTechStack: Tools this unit uses (same sub-fields as above).
- partners: External collaborators or vendors.
- budget: The approximate budget the unit controls.
- newBudgetStartDate: When new funds might become available.
- buyingProcess: Steps specific to this unit’s purchasing cycle (stepName, department, stakeholderRole, influenceScore, stepGoals, expectedOutcomes, averageTimeInDays).
- projects: Ongoing or future projects at the unit level (same sub-fields as accountInsights projects).

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
We want ONLY the "contactsInsights" array in valid JSON format.

contactsInsights fields:
- contactName: Full name of the contact.
- role: Position or title (e.g., “IT Manager”).
- orgUnit: Which department/division they're part of.
- influenceLevel: e.g., "Low", "Medium", or "High".
- contactRoles: e.g. ["Champion", "Technical Evaluator"].
- objectives: Person-level goals or metrics they want to meet.
- motivations: Why they care about a solution.
- keyKPIs: Metrics the contact is directly responsible for.
- criteria: The contact's personal selection criteria.
- painPoints: Individual-level frustrations.
- implications: What happens if these issues aren't solved (for them).
- currentTechStack: Tools this contact personally uses (same sub-fields as above).
- partners: External personal vendor relationships or resources.
- hasBudgetAuthority: Boolean indicating if they can approve spending.
- projectsInvolved: A list of projects they are part of.

JSON STRUCTURE:

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

# =====================================
# PROMPT-BUILDING FUNCTIONS
# =====================================

def get_account_insights_prompt(transcript):
    """
    Builds a prompt for "accountInfo" + "accountInsights" using
    centralized definitions and instructions.
    """
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

from .ai_resquests import call_llm

def get_full_insights(transcript, model="gpt-3.5-turbo"):

    # Prompt 1: accountInfo + accountInsights
    prompt_1 = get_account_insights_prompt(transcript)
    result_1 = call_llm(prompt_1, model=model)
    data_1 = parse_json_with_defaults(result_1)

    # Prompt 2: orgUnitsInsights
    prompt_2 = get_org_units_prompt(transcript)
    result_2 = call_llm(prompt_2, model=model)
    data_2 = parse_json_with_defaults(result_2)

    # Prompt 3: contactsInsights
    prompt_3 = get_contacts_prompt(transcript)
    result_3 = call_llm(prompt_3, model=model)
    data_3 = parse_json_with_defaults(result_3)

    # Merge results
    # Start with a base structure
    final_structure = {
        "accountInfo": {
            "accountName": None,
            "accountType": None,
            "classification": None,
            "employeeCount": 0,
            "annualRevenue": 0,
            "buyingDecisionsLocation": None,
            "parentCompany": {
                "companyName": None,
                "accountId": None
            },
            "orgUnits": []
        },
        "insights": {
            "accountInsights": {},
            "orgUnitsInsights": [],
            "contactsInsights": []
        }
    }

    # If accountInfo + accountInsights was successfully parsed:
    if data_1 and "accountInfo" in data_1 and "insights" in data_1:
        final_structure["accountInfo"] = data_1.get("accountInfo", final_structure["accountInfo"])
        final_structure["insights"]["accountInsights"] = data_1["insights"].get("accountInsights", {})
    else:
        # fallback to empty if not found
        pass

    # If orgUnitsInsights was successfully parsed:
    if data_2 and "orgUnitsInsights" in data_2:
        final_structure["insights"]["orgUnitsInsights"] = data_2["orgUnitsInsights"]

    # If contactsInsights was successfully parsed:
    if data_3 and "contactsInsights" in data_3:
        final_structure["insights"]["contactsInsights"] = data_3["contactsInsights"]

    # Return the final merged JSON
    return final_structure
