COMMON_INSTRUCTIONS = """
    You are an AI assistant that extracts sales qualification data from text and returns structured sales qualification and opportunity insights in JSON format. 
    I will provide you with a sanitized transcript from email conversations, call notes, or a complete call transcript between a sales AE and interlocutors (prospect, client, or partner). 
    You will extract and summarize the relevant information and organize it in the following JSON structure.

    Think of your output as an expanded version of MEDPICC, converted into JSON with clear, actionable insights.

    We specifically categorize insights at different levels:
       1) Account level
       2) Contacts
       3) TechStack
       4) Buying Process
       5) Lead or Opportunity

    Follow these rules:
      1. If data is unclear or missing, use null/0/false/[] as appropriate. 
      2. Do not invent data that is not explicitly stated or reasonably implied.
      3. Provide measurable objectives whenever possible.
      4. Focus on data relevant to sales qualification: pains, goals, budgets, processes, etc.
      5. Return valid JSON matching the exact structures shown, with no extra commentary.
    
    Additional clarifications:
      - For **objectives**, make them measurable and actionable (e.g., “Increase sales by 20% within 6 months”).
      - For **motivations**, specify reasons driving interest (e.g., “Expand market share”).
      - For **implications**, quantify the impact (e.g., “Risk losing 10% of revenue”).
      - For **BuyingProcess**, list an array of the different steps Sales will go through to close a deal, including who the stakeholders are, their role/department, their influence in the process, how they will validate the process, what criteria they will look for, and how long each step might last. This is crucial for qualification, to understand each step, prepare for it, maximize value, and have a clear idea of how long the process will take for forecasting.

       Sub-object example for BuyingProcess:
         - Stakeholder: Role of the person responsible for this step (e.g., "CEO", "Project Manager", "CTO")
         - departmentName: Name of the Account department for this step (e.g., "IT", "Sales", "General Management", etc.)
         - stepDescription: What will be done in this step (e.g., "Demo", "POC", "Legal revision of the contract")
         - stepGoal: What the step aims to achieve (e.g., "Technical validation", "Budget validation")
         - influenceScore: How important this step is for moving forward
         - Criterias: What they will be looking for (e.g., "Is it within budget?", "Does it work in our ecosystem?", "Does it cover all our needs?")
         - KeyKpis: How they will measure success in this step
         - averageTimeInDays: How long this step might take before moving to the next one

      - For **TechStack**: a list of products or solutions the interlocutors mentioned using:
         Sub-object:
           - "techName": Name of the solution
           - "businessGoal": Purpose of using this solution
           - "pros": Positive statements made about this product
           - "improvementPoints": What the product lacks to address all pains
           - "yearsOfUsage": How long they have been using this solution/product, if stated
           - "costs": A list of various costs (e.g., "Subscription cost", "Maintenance cost"), and include amounts if stated
           - "renewalDate": If it's a subscription, when the contract will end

      - For **departmentName**, use one from the list: ["General Management", "Human Resources (HR)", "Finance & Accounting", "Information Technology (IT)", "Marketing & Communications", "Sales & Business Development", "Customer Support & Success", "Operations & Supply Chain", "Legal & Compliance", "Procurement & Vendor Management", "Engineering & R&D", "Product Management", "Data & Analytics", "Security & Risk Management", "Healthcare Administration", "Clinical & Medical Staff", "Retail & Store Operations", "Manufacturing & Production", "Logistics & Transportation", "Construction & Engineering", "Education & Training", "Government & Public Services", "Media & Content Creation"]

      - Each level (Account, OrgUnit, Contact) can have relevant pains, processes, or budget data.
    
    Below is a comprehensive guide if needed:
       1. Account Info + Insights
       2. Org Units Insights
       3. Contacts Insights
       4. Focus on key fields: objectives, painPoints, currentTechStack, buyingProcess, projects, etc.
"""


ACCOUNT_INSIGHTS_DEFINITIONS = """
    We have two main sections to fill in a single JSON:
      1) "accountInfo"
      2) "accountInsights" (All data linked to the entire Account)
    
    ACCOUNT INFO FIELDS:
      - employeeCount: Approximate number of employees, if stated.
      - annualRevenue: Numeric revenue, if stated.
      - buyingDecisions: Whether they have the final authority to make a purchase (True/False), if stated

    ACCOUNT INSIGHTS FIELDS:
      - For **objectives**, make them measurable and actionable (e.g., “Increase sales by 20% within 6 months”).
      - For **motivations**, specify reasons driving interest (e.g., “Expand market share”).
      - For **metrics** 
      - For **painPoints**
      - For **implications**, quantify the impact (e.g., “Risk losing 10% of revenue”).
      - For **partners**

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


ORG_UNITS_DEFINITIONS = """
    Return ONLY "orgUnitsInsights" array in valid JSON.
    Qualification data specific to a given department within the Account.

    orgUnitsInsights fields:
      departmentName, objectives, compellingEvents, motivations,
      painPoints, implications, currentTechStack, partners,
      budget, newBudgetStartDate, buyingProcess

JSON STRUCTURE:

{
  "orgUnitsInsights": [
    {
      "departmentName": "",
      "objectives": [],
      "compellingEvents": [],
      "motivations": [],
      "painPoints": [],
      "implications": [],
      "currentTechStack": [
         {
            "techName": "",
            "businessGoal": "",
            "pros": "",
            "improvementPoints": "",
            "yearsOfUsage": "",
            "costs": "",
            "renewalDate": ""
         }
      ],
      "partners": [],
      "budget": 0,
      "newBudgetStartDate": "",
      "buyingProcess": [
         {
            "Stakeholder": "",
            "departmentName": "",
            "stepDescription": "",
            "stepGoal": "",
            "influenceScore": 0,
            "Criterias": [],
            "KeyKpis": [],
            "averageTimeInDays": 0
         }
      ]
    }
  ]
}
"""


CONTACTS_DEFINITIONS = """
    Return ONLY "contactsInsights" array in valid JSON.
    This array includes all stakeholders in the process, along with their objectives, motivations, KPIs, and personal impact.

    contactsInsights fields:
      contactName, role, orgUnit, influenceLevel,
      contactRoles, objectives (array of {goal, metrics, timeline}),
      motivations, keyKPIs, criteria, painPoints, implications,
      hasBudgetAuthority

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
      "hasBudgetAuthority": false
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
