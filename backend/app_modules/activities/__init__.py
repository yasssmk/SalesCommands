# app_modules/activities/__init__.py
"""
Activity module for app_modules.

Represents operational execution of sales work:
- Meetings, calls, emails, tasks
- Linked to CompanyAccount, Contact(s), User (owner)
- Optionally linked to DecisionCycle/DecisionStep

Uses UUID primary keys for consistency with app_modules.
"""

default_app_config = 'app_modules.activities.apps.ActivitiesConfig'