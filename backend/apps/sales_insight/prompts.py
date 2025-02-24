#Activity Analisys

# =====================================
# CENTRALIZED DEFINITIONS & INSTRUCTIONS
# =====================================
# COMMON_INSTRUCTIONS = """
#     You are an AI assistant that extracts structured sales qualification insights from text. 
#     I will provide you with a sanitized transcript from email conversation, call notes or a complete call transcript between a sales AE and an interlocutor either a prospect, a client or a partner.
#     You will extract and sum up the relevant information for the sales qualification and organize them as explained below; This data will be used later by sales team to spot opportunity, estimate the potential of an account, white space analysis and understand the main pain points and process of an account to make sales strategies around.


#     Produce JSON **only** for the "accountInfo" and "accountInsights" sections, 
#     following these rules:

#     1. If data for a field is not found, fill it with null, 0, false, or an empty array ([]) as appropriate but Feel free to interpret partial statements if it seems reasonable.
#     2. Use arrays or objects exactly as shown in the structure.
#     3. Do not add extra keys. 
#     4. Output must be valid JSON with correct nesting.
# """

COMMON_INSTRUCTIONS = """
    You are an AI assistant that extracts sales qualification data from text and return structured sales qualification insight in JSON format. 
    I will provide you with a sanitized transcript from email conversation, call notes or a complete call transcript between a sales AE and interlocutors either from a prospect or a client companies. 
    You will extract and sum up the relevant information for the sales qualification and organize them as explained below; This data will be used later by sales team to spot sales opportunities, estimate the potential of an account, white space analysis and understand the main pain points and process of an account to make sales strategies around by sales teams. Think like an expanded MEDPICC turn into a JSON.
The structure will have differents levels: 
1.	Account level: Qualification data related to and/or impacting the business as a whole
2.	organizational units: Qualification data related to and/or impacting the specific department mentioned
3.	Contact: Qualification data related to and/or impacting the specific contact.
For each level you’ll look for specific sales qualification information following these rules:
1.	If data for a field is not found (stated or confirmed by the interlocutors), fill it with null, 0, false, or an empty array ([]) as appropriate but feel free to interpret partial statements if it seems reasonable.
2.	Use arrays or objects exactly as shown in the structure.
3.	Do not add extra keys. 
4.	Output must be valid JSON with correct nesting.
Here is a comprehensive guide of the qualification to be adapted for each level if applicable:
1.	Account Information for ICP profiling and Filtering
Role: The purpose of this step is to gather basic account information to determine if the prospect fits the Ideal Customer Profile (ICP). This helps in segmenting and prioritizing leads that are more likely to convert.
2.	Understand Business Goals and Objectives.
Role: This phase involves comprehending the overarching goals and objectives of the business, department, or interlocutor. By understanding their strategic priorities and the metrics they use to measure success, salesperson can tailor your pitch to better align with their needs.
3.	Understand Pains and Challenges to Reach Their Goals and Their Impact
Role: Identify the specific pain points and challenges that the prospect is facing in achieving their business goals. Understanding these issues helps in positioning a solution as a remedy.
4.	Current Status Quo
Role: Understanding the current situation, including their existing solutions and processes. This helps in identifying gaps and opportunities for sales team product or service.
5.	Understand Their Buying Process and Their Stakeholders
Role: Gain insights into the prospect's buying process and identify key stakeholders involved in the decision-making. Knowing this helps in navigating the sales process more effectively.
6.	Did They Already Have or Are They Planning to Make a Purchase to Improve/Solve Challenges Stated
Role: Determine if the prospect has already made or is planning to make a purchase to address their challenges. This helps gauge their readiness to buy and tailor your approach accordingly
"""

ACCOUNT_INSIGHTS_DEFINITIONS = """
    We have two sections to fill in a single JSON object:
    1) "accountInfo"
    2) "accountInsights"

    Short definitions of each field:
    ACCOUNT INFO FIELDS:
    - accountName: The company's official or recognized name.
    - accountType: e.g. is CLIENT, PROSPECT or PARTNER.
    - classification: Segment or size category (e.g. SMB, MIDMARKET, ENTERPRISE).
    - employeeCount: Approximate number of employees in the entire company if stated.
    - annualRevenue: Approximate annual revenue as a numeric value if stated.
    - buyingDecisionsLocation: Where or by whom major purchasing decisions are made. ( e.g Headquarter, parent account ...)
    - parentCompany: If this company is a subsidiary (with "companyName" & "accountId").
    - orgUnits: Array of organizational units (we will fill them in another step, so leave it empty or default).

    ACCOUNT INSIGHTS FIELDS:
    - objectives: Major business goals or outcomes the company wants.
    - compellingEvents: Time-sensitive events or triggers that influence decisions. (e.g new law, new ceo, loss in revenue or quality ...)
    - motivations: Reasons driving their interest in business. ( e.g increase market share, increase marging, be the #1 brand for ..., )
    - keyKPIs: Key performance indicators they follow to measure their success.
    - criteria: High-level conditions or requirements to select a product/solution.
    - painPoints: Main problems or obstacles the entire account faces.
    - implications: Consequences if those pain points are not resolve, best if traduced in quantizable unit ( e.g dollars, time, revenue loss).
    - currentTechStack: Tools or technologies they currently use (with sub-fields):
    - techName: name of the solution they use, businessGoal: What is the reason they use this tool, popularityScore (0-10): Based on the way they describe the product's pros and cons estimate a popularity score fropm 0 (bad) to 10 (great) among the company, pros: What do they like about this product, improvementPoints: What is missing and would help them a lot (reach a 10 score in popularity), yearsOfUsage: Since how many years they have been using this solution if stated, costs: Everything stated reslated to price and contract of the solution, renewalDate: if a subscription contract have they stated when the contract ends.
    - partners: Other external vendors or consulting firms they work with.
    - budget: Estimated total budget for new initiatives.
    - newBudgetStartDate: When a new budget cycle or pool of funds becomes available.
    - buyingProcess: Steps or phases the account goes through to evaluate and purchase solutions (with sub-fields):
    - stepName: arbitrary name of the process, department: what department company, stakeholderRole, influenceScore (0-10): the importance of the role and the weight in the decision, stepGoals: what is the role of this step (e.g IT: check the technical integration within the echosystem, Legal: check the contract...), expectedOutcomes, averageTimeInDays: if stated the average time it takes for this step, this will help the sales team to measure how long take the whole buying process and act accordingly.
    - projects: Determine if the prospect has already made or is planning to make a purchase to address their challenges (with sub-fields):
    - projectName: arbitrary name of the, targetYear: When the purchase is or was planned, keyInitiatives: reason and motivation to make the purches, compellingEvents: did a specific event force them to make this project (e.g: New regulation, event that have negatively impacted the business...), products: What kind of product we are talking about, metrics: What metrics will they use to measure the success of the purchase (e.g productivity, cost, time...), painPoints: What pain points they are trying to resolve, impacts,
        decisionCriteria: what will they be looking at for the choice of solution , hasStarted (bool), relevantDates (milestones), budgetAllocation, estimatedUnitsNeeded,
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

def strip_backticks_and_code_fences(llm_text: str) -> str:
    """
    Removes triple backticks or code fences from the model's response
    so that json.loads(...) won't fail.
    """
    # Quick approach: remove any leading/trailing ``` with optional `json`
    clean = llm_text.strip()
    clean = clean.replace("```json", "").replace("```", "")
    return clean.strip()

from .ai_resquests import call_llm

def get_full_insights(transcript):
    # 1) Make the initial prompt and parse result for Account + Insights
    prompt_1 = get_account_insights_prompt(transcript)
    result_1 = call_llm(prompt_1)
    # Remove any triple-backticks
    result_1_stripped = strip_backticks_and_code_fences(result_1)
    data_1 = parse_json_with_defaults(result_1_stripped)
    print(f"RESULT 1 (stripped): {result_1_stripped}")

    if data_1 is None or "accountInfo" not in data_1 or "insights" not in data_1:
        # Fallback if JSON is invalid or missing top-level "insights"
        fix_prompt_1 = FALLBACK_PROMPT_IF_ERROR.format(malformed_json=result_1_stripped)
        new_result_1 = call_llm(fix_prompt_1)
        new_result_1_stripped = strip_backticks_and_code_fences(new_result_1)
        data_1 = parse_json_with_defaults(new_result_1_stripped)
        print(f"FALLBACK RESULT 1 (stripped): {new_result_1_stripped}")

    # 2) orgUnitsInsights
    prompt_2 = get_org_units_prompt(transcript)
    result_2 = call_llm(prompt_2)
    result_2_stripped = strip_backticks_and_code_fences(result_2)
    data_2 = parse_json_with_defaults(result_2_stripped)
    print(f"RESULT 2 (stripped): {result_2_stripped}")

    if data_2 is None or "orgUnitsInsights" not in data_2:
        fix_prompt_2 = FALLBACK_PROMPT_IF_ERROR.format(malformed_json=result_2_stripped)
        new_result_2 = call_llm(fix_prompt_2)
        new_result_2_stripped = strip_backticks_and_code_fences(new_result_2)
        data_2 = parse_json_with_defaults(new_result_2_stripped)
        print(f"FALLBACK RESULT 2 (stripped): {new_result_2_stripped}")

    # 3) contactsInsights
    prompt_3 = get_contacts_prompt(transcript)
    result_3 = call_llm(prompt_3)
    result_3_stripped = strip_backticks_and_code_fences(result_3)
    data_3 = parse_json_with_defaults(result_3_stripped)
    print(f"RESULT 3 (stripped): {result_3_stripped}")

    if data_3 is None or "contactsInsights" not in data_3:
        fix_prompt_3 = FALLBACK_PROMPT_IF_ERROR.format(malformed_json=result_3_stripped)
        new_result_3 = call_llm(fix_prompt_3)
        new_result_3_stripped = strip_backticks_and_code_fences(new_result_3)
        data_3 = parse_json_with_defaults(new_result_3_stripped)
        print(f"FALLBACK RESULT 3 (stripped): {new_result_3_stripped}")

    # Start with a base final structure
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

    print(f"DATA 1: {data_1}")
    print(f"DATA 2: {data_2}")
    print(f"DATA 3: {data_3}")
    # Merge accountInfo + accountInsights if data_1 is valid
    if data_1 and "accountInfo" in data_1 and "accountInsights" in data_1:
        final_structure["accountInfo"] = data_1.get("accountInfo", final_structure["accountInfo"])
        final_structure["insights"]["accountInsights"] = data_1.get("accountInsights", {})

    # Merge orgUnitsInsights if data_2 is valid
    if data_2 and "orgUnitsInsights" in data_2:
        final_structure["insights"]["orgUnitsInsights"] = data_2["orgUnitsInsights"]

    # Merge contactsInsights if data_3 is valid
    if data_3 and "contactsInsights" in data_3:
        final_structure["insights"]["contactsInsights"] = data_3["contactsInsights"]

    return final_structure