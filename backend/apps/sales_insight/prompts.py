#Activity Analisys



EXPECTED_OUTCOME = {
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
    "orgUnits": [
      {
        "organizationName": "",
        "unitType": "",
        "standardDepartment": "",
        "estimatedEmployeeCount": 0,
        "budget": 0,
        "parentOrganizationUnit": ""
      }
    ]
  },
  "insights" : {
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
        "buyingProcess": {
            [
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
        },
        "projects": [
            {
                "projectName": "",
                "targetYear": 0,
                "keyInitiatives": [],
                "compellingEvents": [],
                "products": [],
                "metrics": [],
                "painPoints": [],
                "impacts":[],
                "decisionCriteria": [],
                "hasStarted": False,
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
                "estimatedUnitsNeeded":0,
                "unitOfMeasure": "",                
                "stakeholders":[
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
        ],
    },
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
        "budgetThresholds": 0,
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
            "hasStarted": False,
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
  ],
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
        "hasBudgetAuthority": False,
        "projectsInvolved": [
          {
            "projectName": ""
          }
        ]
      }
    ]
  }
}

def get_account_insights_prompt(transcript):
    """
    Builds a prompt for *accountInfo* and *accountInsights* 
    with placeholders for null if not found.
    """
    return f"""You are an AI assistant that extracts structured sales insights from text. 
        I will provide you with a sanitized transcript from email conversation, call notes or a complete call transcript. 
        Produce JSON **only** for the "accountInfo" and "accountInsights" sections, 
        following these rules:

        1. If data for a field is not found, fill it with null, 0, false, or an empty array ([]) as appropriate.
        2. Use arrays or objects exactly as shown in the structure.
        3. Do not add extra keys. 
        4. Output must be valid JSON with correct nesting.

        Here are one-sentence definitions for each field you must fill:

        - **accountName**: The company's official or recognized name.  
        - **accountType**: The type of account (CLIENT, PROSPECT, PARTNER, etc.).  
        - **classification**: Segment or size category (e.g. SMB, MIDMARKET, ENTERPRISE).  
        - **employeeCount**: Approximate number of employees in the entire company.  
        - **annualRevenue**: Approximate annual revenue in numeric form.  
        - **buyingDecisionsLocation**: Where or by whom major purchasing decisions are made.  
        - **parentCompany**: The larger entity if this company is a subsidiary (companyName & accountId).  
        - **orgUnits**: (We will fill actual details later in another step, so leave the array structure intact but empty or default.)
        
        **accountInsights** definitions:  
        - **objectives**: Major business goals or outcomes the company wants.  
        - **compellingEvents**: Time-sensitive events or triggers that influence decisions.  
        - **motivations**: Reasons driving their interest in new solutions.  
        - **keyKPIs**: Key performance indicators they care about.  
        - **criteria**: High-level conditions or requirements to select a product/solution.  
        - **painPoints**: Main problems or obstacles the entire account faces.  
        - **implications**: Consequences if those pain points are not resolved.  
        - **currentTechStack**: Tools/technologies they currently use.  
        - **techName**: Name of the tool/technology.  
        - **businessGoal**: The purpose of using this tool.  
        - **popularityScore**: A numeric rating (0-10) of how widely it’s adopted internally.  
        - **pros**: Positive aspects or benefits.  
        - **improvementPoints**: Potential improvements.  
        - **yearsOfUsage**: How long they have been using it.  
        - **costs**: Any known costs or fees.  
        - **renewalDate**: Date when the contract or subscription might expire.  
        - **partners**: Other external vendors or consulting firms they work with.  
        - **budget**: Estimated total budget for new initiatives.  
        - **newBudgetStartDate**: When a new budget cycle or pool of funds becomes available.  
        - **buyingProcess**: Steps or phases the account goes through to evaluate and purchase solutions.  
        - **stepName**: A short label for the step.  
        - **department**: Which department drives this step.  
        - **stakeholderRole**: Who is primarily responsible.  
        - **influenceScore**: A 0-10 rating of how influential that step’s stakeholders are.  
        - **stepGoals**: What they want to achieve in this step.  
        - **expectedOutcomes**: The desired or expected results.  
        - **averageTimeInDays**: Typical duration of this step.  
        - **projects**: Upcoming or ongoing initiatives relevant to the entire account.  
        - **projectName**: A short descriptive name.  
        - **targetYear**: Which year this project is aimed for.  
        - **keyInitiatives**: Sub-goals or major tasks.  
        - **compellingEvents**: Specific triggers for this project.  
        - **products**: Relevant solutions or product categories they consider.  
        - **metrics**: How success is measured.  
        - **painPoints**: Problems this project aims to solve.  
        - **impacts**: Potential effect of solving or ignoring these problems.  
        - **decisionCriteria**: Specific requirements to go forward.  
        - **hasStarted**: Boolean indicating if the project has already begun.  
        - **relevantDates**: Important milestones (startDate, contractSignature, goLive, etc.).  
        - **budgetAllocation**: The money set aside for this project.  
        - **estimatedUnitsNeeded**: Estimated quantity (units, licenses, seats).  
        - **unitOfMeasure**: Type of unit (e.g., seats, devices, etc.).  
        - **stakeholders**: People involved in this project.  
            - **name**: Person’s name.  
            - **role**: Their function (e.g., manager, sponsor).  
            - **influenceLevel**: L, M, or H.  
            - **rolesInProcess**: Specific responsibilities in the project.  
            - **contactInfo**: Basic info (email, phone).


        JSON STRUCTURE to fill:

        {{
        "accountInfo": {{
            "accountName": "",
            "accountType": "",
            "classification": "",
            "employeeCount": 0,
            "annualRevenue": 0,
            "buyingDecisionsLocation": "",
            "parentCompany": {{
            "companyName": "",
            "accountId": ""
            }},
            "orgUnits": []
        }},
        "insights": {{
            "accountInsights": {{
            "objectives": [],
            "compellingEvents": [],
            "motivations": [],
            "keyKPIs": [],
            "criteria": [],
            "painPoints": [],
            "implications": [],
            "currentTechStack": [
                {{
                "techName": "",
                "businessGoal": "",
                "popularityScore": 0,
                "pros": "",
                "improvementPoints": "",
                "yearsOfUsage": "",
                "costs": [],
                "renewalDate": ""
                }}
            ],
            "partners": [],
            "budget": 0,
            "newBudgetStartDate": "",
            "buyingProcess": [
                {{
                "stepName": "",
                "department": "",
                "stakeholderRole": "",
                "influenceScore": 0,
                "stepGoals": [],
                "expectedOutcomes": [],
                "averageTimeInDays": 0
                }}
            ],
            "projects": [
                {{
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
                "relevantDates": {{
                    "startDate": "",
                    "technicalValidation": "",
                    "solutionValidation": "",
                    "quoteValidation": "",
                    "contractSignature": "",
                    "implementation": "",
                    "goLive": "",
                    "otherDates": []
                }},
                "budgetAllocation": 0,
                "estimatedUnitsNeeded": 0,
                "unitOfMeasure": "",
                "stakeholders": [
                    {{
                    "name": "",
                    "role": "",
                    "influenceLevel": "",
                    "rolesInProcess": [],
                    "contactInfo": {{
                        "email": "",
                        "phone": ""
                    }}
                    }}
                ]
                }}
            ]
            }}
        }}
        }}

        TRANSCRIPT:
        \"\"\"{transcript}\"\"\"
        """

def get_org_units_prompt(transcript):
    """
    Prompt for *orgUnitsInsights* only.
    """
    return f"""You are an AI assistant that extracts organizational unit insights from text. 
        Return only the "orgUnitsInsights" array in valid JSON format. 
        If no data is found for a field, use null, false, 0, or empty structures as appropriate.

        an orgUnit is a pecific unit within a company or a department (e.g Human ressource, or Payroll or IT or development team...).
        Here are definitions of each field at the org-unit level:

        - **organizationName**: The unit’s name (e.g., “Engineering Dept”).  
        - **unitType**: DEPARTMENT, DIVISION, TEAM, etc.  
        - **objectives**: Key goals for this unit.  
        - **compellingEvents**: Time-based triggers for this unit's decisions.  
        - **motivations**: Specific drivers within this unit.  
        - **keyKPIs**: The KPIs they track.  
        - **criteria**: Requirements for solutions or changes.  
        - **painPoints**: Challenges or issues the unit faces.  
        - **implications**: Consequences if those issues aren’t solved.  
        - **currentTechStack**: Tools used by this unit.  
        - **partners**: External collaborators or vendors.  
        - **budget**: The approximate budget the unit controls.  
        - **newBudgetStartDate**: When new funds might become available.  
        - **buyingProcess**: Steps specific to this unit’s purchasing cycle.  
        - **stepName**: e.g., “Evaluation,” “Approval,” etc.  
        - **department**: Which part of the org is involved.  
        - **stakeholderRole**: The role in that step.  
        - **influenceScore**: 0-10 rating.  
        - **stepGoals**: What they want to achieve in this step.  
        - **expectedOutcomes**: The desired results.  
        - **averageTimeInDays**: How long it usually takes.  
        - **projects**: Ongoing or future projects at the unit level.  
        - (same fields as in `accountInsights.projects`, e.g., `projectName`, `hasStarted`, `budgetAllocation`, etc.)

        JSON structure to fill:

        {{
        "orgUnitsInsights": [
            {{
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
                {{
                "techName": "",
                "businessGoal": "",
                "popularityScore": 0,
                "pros": "",
                "improvementPoints": "",
                "yearsOfUsage": "",
                "costs": [],
                "renewalDate": ""
                }}
            ],
            "partners": [],
            "budget": 0,
            "newBudgetStartDate": "",
            "buyingProcess": [
                {{
                "stepName": "",
                "department": "",
                "stakeholderRole": "",
                "influenceScore": 0,
                "stepGoals": [],
                "expectedOutcomes": [],
                "averageTimeInDays": 0
                }}
            ],
            "projects": [
                {{
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
                "relevantDates": {{
                    "startDate": "",
                    "technicalValidation": "",
                    "solutionValidation": "",
                    "quoteValidation": "",
                    "contractSignature": "",
                    "implementation": "",
                    "goLive": "",
                    "otherDates": []
                }},
                "budgetAllocation": 0,
                "estimatedUnitsNeeded": 0,
                "unitOfMeasure": "",
                "stakeholders": [
                    {{
                    "name": "",
                    "role": "",
                    "influenceLevel": "",
                    "rolesInProcess": [],
                    "contactInfo": {{
                        "email": "",
                        "phone": ""
                    }}
                    }}
                ]
                }}
            ]
            }}
        ]
        }}

        TRANSCRIPT:
        \"\"\"{transcript}\"\"\"
        """

def get_contacts_prompt(transcript):
    """
    Prompt for *contactsInsights* only.
    """
    return f"""You are an AI assistant that extracts contact-level insights from text. 
        Return only the "contactsInsights" array in valid JSON format. 
        If no data is found, place null/empty arrays.

        Use the definitions below to guide you:

        - **contactName**: Full name or the reference used in the transcript.  
        - **role**: The position (e.g., “IT Manager”).  
        - **orgUnit**: Which department or division this contact is part of, if known.  
        - **influenceLevel**: Could be “Low,” “Medium,” or “High.”  
        - **contactRoles**: A list of roles this contact might play (e.g. “Champion,” “Technical Evaluator”).  
        - **objectives**: Person-level goals (what they personally want or need).  
        - **motivations**: Why they care about a solution.  
        - **keyKPIs**: Metrics the contact is directly responsible for.  
        - **criteria**: The contact’s personal selection criteria.  
        - **painPoints**: Individual-level frustrations or issues.  
        - **implications**: Potential consequences for this person if issues aren’t solved.  
        - **currentTechStack**: Tools this contact uses directly.  
        - **partners**: External resources or personal vendor relationships.  
        - **hasBudgetAuthority**: Boolean indicating if they can approve spending.  
        - **projectsInvolved**: Which major projects they’re participating in.

        JSON structure:

        {{
        "contactsInsights": [
            {{
            "contactName": "",
            "role": "",
            "orgUnit": "",
            "influenceLevel": "",
            "contactRoles": [],
            "objectives": [
                {{
                "goal": "",
                "metrics": "",
                "timeline": []
                }}
            ],
            "motivations": [],
            "keyKPIs": [],
            "criteria": [],
            "painPoints": [],
            "implications": [],
            "currentTechStack": [
                {{
                "techName": "",
                "businessGoal": "",
                "popularityScore": 0,
                "pros": "",
                "improvementPoints": "",
                "yearsOfUsage": "",
                "costs": [],
                "renewalDate": ""
                }}
            ],
            "partners": [],
            "hasBudgetAuthority": false,
            "projectsInvolved": [
                {{
                "projectName": ""
                }}
            ]
            }}
        ]
        }}

        TRANSCRIPT:
        \"\"\"{transcript}\"\"\"
        """


