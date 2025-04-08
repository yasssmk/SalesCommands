COMMON_INSTRUCTIONS = """
    You are an AI assistant that extracts sales qualification data from text and returns structured sales qualification and opportunity insights in JSON format. 
    I will provide you with a sanitized transcript from email conversations, call notes, or a complete call transcript between a sales AE and interlocutors (prospect, client, or partner). 
    You will extract and summarize the relevant information and organize it in the following JSON structure.

    Think of your output as an expanded version of MEDPICC, converted into JSON with clear, actionable insights.

    We specifically categorize insights at different levels:
       1) Account level
       2) Contacts level
       3) TechStack
       4) Buying Process


    Follow these rules:
      1. If data is unclear or missing, use null/0/false/[] as appropriate. 
      2. Do not invent data that is not explicitly stated or reasonably implied.
      3. Provide measurable objectives whenever possible.
      4. Focus on data relevant to sales qualification: pains, goals, budgets, processes, etc.
      5. Return valid JSON matching the exact structures shown, with no extra commentary.

"""


ACCOUNT_INSIGHTS_DEFINITIONS = """
    We have two main sections to fill in a single JSON:
      1) "accountInfo"
      2) "accountInsights"
    
    ACCOUNT INFO FIELDS:
      - employeeCount: Approximate number of employees, if stated.
      - annualRevenue: Numeric revenue, if stated.
      - buyingDecisions: Whether they have the final authority to make a purchase (True/False), if stated

    ACCOUNT INSIGHTS FIELDS:
      - For **objectives**, make them measurable and actionable (e.g., “Increase sales by 20% within 6 months”).
      - For **motivations**, specify reasons driving interest (e.g., “Expand market share”).
      - For **metrics** , Key performance indicators copmapny follows to measure its success (e.g., growth rate, operational efficiency, customer retention).
      - For **painPoints**, Main problems or obstacles company face (e.g., manual data entry, inefficient workflow).
      - For **implications**, quantify the impact (e.g., “Risk losing 10% of revenue”).
      - For **partners**, Other external vendors or consulting firms they work with.

    JSON STRUCTURE TO RETURN (for this prompt):

    {
      "accountInfo": {
          "employeeCount": 0,
          "annualRevenue": 0,
          "buyingDecisions": "",
      },
      "insights": {
          "accountInsights": {
              "objectives": [],
              "motivations": [],
              "metrics":[],
              "painPoints": [],
              "implications": [],
              "partners": [],
          }
      }
    }
"""

CONTACTS_DEFINITIONS = """
    Return ONLY "contactsInsights" array in valid JSON.
    This array includes all stakeholders in the process, along with their objectives, motivations, KPIs, and personal impact.

     CONTACT INSIGHTS FIELDS:
      - For **ContactName**, Full name of the contact if stated.
      - For **jobTitle**, Name of the contact position in the company if stated.
      - For **department**, Name of the department contact works if stated, use one from the list: ["General Management", "Human Resources (HR)", "Finance & Accounting", "Information Technology (IT)", "Marketing & Communications", "Sales & Business Development", "Customer Support & Success", "Operations & Supply Chain", "Legal & Compliance", "Procurement & Vendor Management", "Engineering & R&D", "Product Management", "Data & Analytics", "Security & Risk Management", "Healthcare Administration", "Clinical & Medical Staff", "Retail & Store Operations", "Manufacturing & Production", "Logistics & Transportation", "Construction & Engineering", "Education & Training", "Government & Public Services", "Media & Content Creation"]
      - For **objectives**, personal objectives for the contact or it´s team if stated. make them measurable and actionable (e.g., “Increase sales by 20% within 6 months”).
      - For **motivations**, personal motivations for the contact or it´s team if stated. specify reasons driving interest (e.g., “Expand market share”).
      - For **metrics** , personal Key performance indicators they follow to measure their success for the contact or it´s team (e.g., growth rate, operational efficiency, customer retention).
      - For **painPoints**, Main problems or obstacles contact or it´s team face (e.g., manual data entry, inefficient workflow).
      - For **implications**, quantify the impact for the contact or it´s team (e.g., “Risk increasing 10% of work load”).
      - For **hasBudgetAuthority**, Does the contact has the Authority to make a purchase?

SAMPLE JSON:

{
  "contactsInsights": [
    {
      "contactName": "",
      "jobTitle": "",
      "department":,
      "objectives": [],
      "motivations": [],
      "metrics": [],
      "painPoints": [],
      "implications": [],
      "hasBudgetAuthority": false,
    }
  ]
}
"""

TECH_STACK_DEFINITION = """
    Return ONLY "TechStack" array in valid JSON.
    This array includes all product and solution the company is using.

    TECH STACK FIELDS:
      - For **TechtName**, Name of the product or technology.
      - For **purpose**, The reason of their purchase or business objective expected using this product/technology.
      - For **pros**, Anything they like or are satisfied about this product/technology
      - For **improvementPoints**, Anything they would like the product-technology to do or any pain point regarding its usage.
      - For **yearsOfUsage**, For how long they have been using this prodcut/technology, if stated.
      - For **costs** , Any costs related to the product/technology. State the name of the cost then, only if stated the price. (e.g., subcription price: 3000$ per month, maintenance cost).
      - For **renewalDate**, Only is technology is a subscription and only if stated the date of the comtact renewal (e.g, November 2025)

    {
      "techStack": [
         {
            "techName": "",
            "purpose":[],
            "pros": [],
            "improvementPoints": [],
            "yearsOfUsage": null,
            "costs": [],
            "renewalDate": ""
         }
      ]
    }


"""

BUYING_PROCESS_DEFINITION = """
  Return ONLY "buyingProcess" array in valid JSON.
  This array includes all steps the company will go through to close a deal.
  This is crucial for qualification, to understand each step, prepare for it, maximize value, and have a clear idea of how long the process will take for forecasting.

  BUYING PROCESS FIELDS:
    - For **stakeholder**, Role of the person responsible for this step (e.g., "CEO", "Project Manager", "CTO")
    - For **department**, Name of the department contact works if stated, use one from the list: ["General Management", "Human Resources (HR)", "Finance & Accounting", "Information Technology (IT)", "Marketing & Communications", "Sales & Business Development", "Customer Support & Success", "Operations & Supply Chain", "Legal & Compliance", "Procurement & Vendor Management", "Engineering & R&D", "Product Management", "Data & Analytics", "Security & Risk Management", "Healthcare Administration", "Clinical & Medical Staff", "Retail & Store Operations", "Manufacturing & Production", "Logistics & Transportation", "Construction & Engineering", "Education & Training", "Government & Public Services", "Media & Content Creation"]
    - For **stepDescription**, What will be done in this step (e.g., "Demo", "POC", "Legal revision of the contract")
    - For **stepGoal**, What the step aims to achieve (e.g., "Technical validation", "Budget validation")
    - For **influenceScore**, How important this step is for moving forward
    - For **criterias**, What they will be looking for (e.g., "Is it within budget?", "Does it work in our ecosystem?", "Does it cover all our needs?")
    - For **metrics**, Key performance indicators they follow to measure their success in this step (e.g., growth rate, operational efficiency, customer retention).
    - For **averageTimeInDays**, How long this step might take before moving to the next one.

  {
    "buyingProcess": 
      [
        {
          "stakeholder": "",
          "department": "",
          "stepDescription": "",
          "stepGoal": "",
          "influenceScore": 0,
          "criterias": [],
          "metrics": [],
          "averageTimeInDays": 0
        }
      ]
  }

"""

LEADS_DEFINITION = """
This applies when the Company, OrgUnit, or Contact is aware of a specific pain point and is considering buying a solution in the future.

SAMPLE JSON:

{
  "LeadsInsights": [
    {
      "CompelingEvents": [],
      "PainPoints": [],
      "AwarenessLevel": "",
      "PlanningToChangeOrBuy": false,
      "ApproxPurchaseDate": ""
    }
  ]
}
"""


OPPORTUNITY_DEFINITION = """
This data will feed the Opportunity and help the AE prepare upcoming steps, maximize value, and anticipate any risks.

Fields:
- current_step: The goal of the meeting/activity if stated
- next: {
    "who": "",
    "expectedTime": "",
    "valueToShow": ""
  }
- Budget
- DoesOurSolutionCoverExpectations
- valueWantedThisStep: []
- Risks: {
    "competitors": [],
    "worries": [],
    "otherRisks": [],
    "unansweredQuestions": []
}

Example JSON structure (final shape might vary):
{
  "OpportunityInsights": {
    "current_step": "",
    "next": {
      "who": "",
      "expectedTime": "",
      "valueToShow": ""
    },
    "CompelingEvents": [],
    "budget": 0,
    "DoesOurSolutionCoverExpectations": false,
    "valueWantedThisStep": [],
    "Risks": {
      "competitors": [],
      "worries": [],
      "otherRisks": [],
      "unansweredQuestions": []
    }
  }
}
"""

FALLBACK_PROMPT_IF_ERROR = """\
You provided invalid or incomplete JSON. 
Please correct it so it is valid JSON with proper braces and no repeated or missing keys.

Original (malformed) JSON:
{malformed_json}

Return ONLY valid JSON. Do not add extra commentary.
"""



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

def get_contacts_prompt(transcript):
    """
    Builds a prompt for "contactsInsights" only, using centralized definitions.
    """
    return f"""{COMMON_INSTRUCTIONS}
        {CONTACTS_DEFINITIONS}
        Return only the 'contactsInsights' array in valid JSON.
        TRANSCRIPT:
        \"\"\"{transcript}\"\"\""""

def get_techstack_prompt(transcript):
    """
    Builds a prompt for "TechStack" only, using centralized definitions.
    """
    return f"""{COMMON_INSTRUCTIONS}
        {TECH_STACK_DEFINITION}
        Return only the 'techStack' array in valid JSON.
        TRANSCRIPT:
        \"\"\"{transcript}\"\"\""""

def get_buying_process_prompt(transcript):
    """
    Builds a prompt for "buyingProcess" only, using centralized definitions.
    """
    return f"""{COMMON_INSTRUCTIONS}
        {BUYING_PROCESS_DEFINITION}
        Return only the 'buyingProcess' array in valid JSON.
        TRANSCRIPT:
        \"\"\"{transcript}\"\"\""""



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


def get_full_insights(transcript):
    """ Extracts all qualification data from a transcript """

    # 1) Extract Account Insights
    prompt_1 = get_account_insights_prompt(transcript)
    data_1 = parse_and_fallback_if_needed(llm_service.call_llm(user_prompt=prompt_1,system_message=system_message), prompt_1)

    # 2) Extract Contacts Insights
    prompt_2 = get_contacts_prompt(transcript)
    data_2 = parse_and_fallback_if_needed(llm_service.call_llm(user_prompt=prompt_2,system_message=system_message), prompt_2)

    # 3) Extract teckStack Insights
    prompt_3 = get_techstack_prompt(transcript)
    data_3 = parse_and_fallback_if_needed(llm_service.call_llm(user_prompt=prompt_3,system_message=system_message), prompt_3)

    #4) Extract Buying Process Insights
    prompt_4 = get_buying_process_prompt(transcript)
    data_4 = parse_and_fallback_if_needed(llm_service.call_llm(user_prompt=prompt_4,system_message=system_message), prompt_4)


    # Base JSON structure
    final_structure = {
        "accountInfo": data_1.get("accountInfo", {}),
        "insights": {
            "accountInsights": data_1.get("accountInsights", {}),
            "contactsInsights": data_2.get("contactsInsights", []),
            "techStack": data_3.get("techStack", []),	
            "buyingProcess": data_4.get("buyingProcess", []),
        }
    }
    
    print("Final JSON structure:", final_structure)
    
    return final_structure