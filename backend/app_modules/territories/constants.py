# app_modules/territories/constants.py
"""
Territory module constants.

Per the project rule, module-level magic values live in the model folder's
``constants.py`` rather than as bare literals in the code.
"""

# Hard cap on the number of ids accepted by the territory bulk-delete endpoint.
BULK_DELETE_MAX_IDS = 500
