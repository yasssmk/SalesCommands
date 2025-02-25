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
    You are an AI assistant that extracts sales qualification data from text and returns structured sales qualification insight in JSON format. 
    I will provide you with a sanitized transcript from email conversations, call notes, or a complete call transcript between a sales AE and interlocutors, either from prospect or client companies. 
    You will extract and summarize the relevant information for sales qualification and organize them as explained below. This data will be used later by the sales team to spot opportunities, estimate potential, analyze white space, and make strategic decisions around accounts.
    Think of your output as an expanded version of MEDPICC, turned into JSON format, with clear and actionable insights.
    The structure will have different levels: 
        1. Account level: Qualification data related to and/or impacting the business as a whole.
        2. Organizational units: Qualification data related to and/or impacting the specific department mentioned.
        3. Contact: Qualification data related to and/or impacting the specific contact.
    Here are the rules:
        1. If any data is missing or unclear, use `null`, `0`, `false`, or `[]` (empty array) as appropriate, but make logical inferences where possible.
        2. Focus on providing actionable, detailed insights—specifically objectives, pain points, and impacts. For example, if an objective is mentioned, describe it in actionable terms with clear metrics or timelines where possible.
        3. Avoid assuming data that isn’t explicitly mentioned; however, interpret partial statements logically to provide insights based on context.
        4. Ensure that the format adheres strictly to the required JSON schema.
        5. Avoid unnecessary commentary or assumptions in your responses. Stick to the data that is given and inferred in the context.
    Additional clarifications:
        - For **objectives**, make them measurable and actionable. For example, "Increase sales by 20% over the next quarter" rather than vague statements like "increase sales."
        - For **motivations**, clearly describe the reasons driving the company's business interest. For example, "Increase market share" or "Improve product quality."
        - For **implications**, quantify the impact wherever possible. For instance, "If this pain point is not resolved, the company risks a 10% revenue loss."
        - Be mindful of **role-specific insights** and **departmental segmentation**. For example, when providing insights related to an individual, link them to their specific department or role within the company (e.g., Marketing, IT, etc.).
    Here is a comprehensive guide of the qualification to be adapted for each level if applicable:
        1. Account Information for ICP profiling and Filtering
        Role: The purpose of this step is to gather basic account information to determine if the prospect fits the Ideal Customer Profile (ICP). This helps in segmenting and prioritizing leads that are more likely to convert.
        2. Understand Business Goals and Objectives.
        Role: This phase involves comprehending the overarching goals and objectives of the business, department, or interlocutor. By understanding their strategic priorities and the metrics they use to measure success, the salesperson can tailor your pitch to better align with their needs.
        3. Understand Pains and Challenges to Reach Their Goals and Their Impact
        Role: Identify the specific pain points and challenges that the prospect is facing in achieving their business goals. Understanding these issues helps in positioning a solution as a remedy.
        4. Current Status Quo
        Role: Understanding the current situation, including their existing solutions and processes. This helps in identifying gaps and opportunities for sales team products or services.
        5. Understand Their Buying Process and Their Stakeholders
        Role: Gain insights into the prospect's buying process and identify key stakeholders involved in the decision-making. Knowing this helps in navigating the sales process more effectively.
        6. Did They Already Have or Are They Planning to Make a Purchase to Improve/Solve Challenges Stated
        Role: Determine if the prospect has already made or is planning to make a purchase to address their challenges. This helps gauge their readiness to buy and tailor your approach accordingly.
"""

ACCOUNT_INSIGHTS_DEFINITIONS = """
    We have two sections to fill in a single JSON object:
    1) "accountInfo"
    2) "accountInsights"

    Short definitions of each field:
    ACCOUNT INFO FIELDS:
    - accountName: The company's official or recognized name.
    - accountType: e.g. CLIENT, PROSPECT, or PARTNER.
    - classification: Segment or size category (e.g. SMB, MIDMARKET, ENTERPRISE).
    - employeeCount: Approximate number of employees in the entire company if stated.
    - annualRevenue: Approximate annual revenue as a numeric value if stated.
    - buyingDecisionsLocation: Where or by whom major purchasing decisions are made (e.g., Headquarter, parent account ...).
    - parentCompany: If this company is a subsidiary (with "companyName" & "accountId").
    - orgUnits: Array of organizational units (we will fill them in another step, so leave it empty or default).

    ACCOUNT INSIGHTS FIELDS:
    - objectives: Major business goals or outcomes the company wants. Please ensure they are actionable and measurable (e.g., “Increase revenue by 15% within 6 months”).
    - compellingEvents: Time-sensitive events or triggers that influence decisions (e.g., new law, new CEO, loss in revenue or quality).
    - motivations: Reasons driving their interest in business (e.g., increase market share, reduce operational costs, become an industry leader).
    - keyKPIs: Key performance indicators they follow to measure their success (e.g., growth rate, operational efficiency, customer retention).
    - criteria: High-level conditions or requirements to select a product/solution.
    - painPoints: Main problems or obstacles the entire account faces (e.g., manual data entry, inefficient workflow).
    - implications: Consequences if those pain points are not resolved, quantified where possible (e.g., a 10% decrease in sales if this issue isn't addressed).
    - currentTechStack: Tools or technologies they currently use, If the duration of usage ("yearsOfUsage") is not mentioned, leave the field null or empty. Do not invent this data. (with sub-fields):
      - techName: Name of the solution they use, businessGoal: What is the reason they use this tool, popularityScore (0-10): Based on the way they describe the product's pros and cons, estimate a popularity score from 0 (bad) to 10 (great) among the company, pros: What do they like about this product, improvementPoints: What is missing and would help them a lot (to reach a 10 score in popularity), yearsOfUsage: Since how many years they have been using this solution (only if stated, do not invent the data), costs: Everything stated related to price and contract of the solution, renewalDate: If a subscription contract, have they stated when the contract ends.
    - partners: Other external vendors or consulting firms they work with.
    - budget: Estimated total budget for new initiatives.
    - newBudgetStartDate: When a new budget cycle or pool of funds becomes available.
    - buyingProcess: Steps or phases the account goes through to evaluate and purchase solutions (with sub-fields):
      - stepName: Arbitrary name of the process, department: What department of the company, stakeholderRole, influenceScore (0-10): The importance of the role and the weight in the decision, stepGoals: What is the role of this step (e.g., IT: check the technical integration within the ecosystem), expectedOutcomes: Expected results of this step, averageTimeInDays: If stated, the average time it takes for this step.

    - projects: Determine if the prospect has already made or is planning to make a purchase to address their challenges, If the duration of usage ("yearsOfUsage") is not mentioned, leave the field null or empty. Do not invent this data. (with sub-fields):
      - projectName: Arbitrary name of the project, targetYear: When the purchase is or was planned (do not invent the data), keyInitiatives: Reason and motivation to make the purchase, compellingEvents: Did a specific event force them to make this project (e.g., new regulation, event negatively impacting the business), products: What kind of product we are talking about, metrics: What metrics will they use to measure the success of the purchase (e.g., productivity, cost, time), painPoints: What pain points they are trying to resolve, impacts, decisionCriteria: What will they be looking at for the choice of solution, hasStarted (bool), relevantDates (milestones), budgetAllocation, estimatedUnitsNeeded, unitOfMeasure, and stakeholders who are involved.

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
- currentTechStack: Tools this unit uses, If the duration of usage ("yearsOfUsage") is not mentioned, leave the field null or empty. Do not invent this data. (same sub-fields as above).
- partners: External collaborators or vendors.
- budget: The approximate budget the unit controls.
- newBudgetStartDate: When new funds might become available.
- buyingProcess: Steps specific to this unit’s purchasing cycle (stepName, department, stakeholderRole, influenceScore, stepGoals, expectedOutcomes, averageTimeInDays).
- projects: past,ongoing or future projects at the unit level,  If the duration of usage ("yearsOfUsage") is not mentioned, leave the field null or empty. Do not invent this data. (same sub-fields as accountInsights projects).

Ensure that each unit’s objectives, pain points, and buying process are clearly tied to their respective department. Each organizational unit should have detailed, actionable insights specific to their role within the company, such as technology needs, project goals, and KPIs.

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
- currentTechStack: Tools this contact personally uses, If the duration of usage ("yearsOfUsage") is not mentioned, leave the field null or empty. Do not invent this data. (same sub-fields as above).
- partners: External personal vendor relationships or resources.
- hasBudgetAuthority: Boolean indicating if they can approve spending.
- projectsInvolved: A list of projects they are part of.

Ensure that you are linking each contact’s objectives and pain points directly to their specific role, responsibilities, and the overall departmental goals. Focus on how the contact’s decisions impact the purchasing process, and quantify the implications where possible.

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

from ai_resquests import call_llm

def get_full_insights(transcript):
    # 1) Make the initial prompt and parse result for Account + Insights
    prompt_1 = get_account_insights_prompt(transcript)
    result_1 = call_llm(prompt_1)
    # Remove any triple-backticks
    result_1_stripped = strip_backticks_and_code_fences(result_1)
    data_1 = parse_json_with_defaults(result_1_stripped)

    if data_1 is None or "accountInfo" not in data_1 or "insights" not in data_1:
        # Fallback if JSON is invalid or missing top-level "insights"
        fix_prompt_1 = FALLBACK_PROMPT_IF_ERROR.format(malformed_json=result_1_stripped)
        new_result_1 = call_llm(fix_prompt_1)
        new_result_1_stripped = strip_backticks_and_code_fences(new_result_1)
        data_1 = parse_json_with_defaults(new_result_1_stripped)

    # 2) orgUnitsInsights
    prompt_2 = get_org_units_prompt(transcript)
    result_2 = call_llm(prompt_2)
    result_2_stripped = strip_backticks_and_code_fences(result_2)
    data_2 = parse_json_with_defaults(result_2_stripped)

    if data_2 is None or "orgUnitsInsights" not in data_2:
        fix_prompt_2 = FALLBACK_PROMPT_IF_ERROR.format(malformed_json=result_2_stripped)
        new_result_2 = call_llm(fix_prompt_2)
        new_result_2_stripped = strip_backticks_and_code_fences(new_result_2)
        data_2 = parse_json_with_defaults(new_result_2_stripped)

    # 3) contactsInsights
    prompt_3 = get_contacts_prompt(transcript)
    result_3 = call_llm(prompt_3)
    result_3_stripped = strip_backticks_and_code_fences(result_3)
    data_3 = parse_json_with_defaults(result_3_stripped)

    if data_3 is None or "contactsInsights" not in data_3:
        fix_prompt_3 = FALLBACK_PROMPT_IF_ERROR.format(malformed_json=result_3_stripped)
        new_result_3 = call_llm(fix_prompt_3)
        new_result_3_stripped = strip_backticks_and_code_fences(new_result_3)
        data_3 = parse_json_with_defaults(new_result_3_stripped)

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