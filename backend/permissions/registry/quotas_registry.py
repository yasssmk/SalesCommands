"""
Quotas Registry — permissions for personal Sales objectives.

Product model: a quota is a PERSONAL planning tool. Every user manages THEIR
OWN objectives (create / update / delete = 'mine' for all tiers); nobody writes
another user's objective. Reads widen with the tier — individual sees their own,
a manager reads their team's, an admin reads the whole client. This read pattern
mirrors END_USERS_REGISTRY['teams'] (a manager's read widening beyond 'mine'),
here individual 'mine' -> manager 'team' -> admin 'client'.
"""

QUOTAS_REGISTRY = {
    'quotas': {
        'create': {
            'admin': 'mine',        # Everyone creates their OWN objectives only
            'manager': 'mine',
            'individual': 'mine',
        },
        'read': {
            'admin': 'client',      # Admin reads all objectives in the client
            'manager': 'team',       # Manager reads their team's objectives
            'individual': 'mine',    # Individual reads only their own
        },
        'update': {
            'admin': 'mine',        # Nobody edits someone else's objective
            'manager': 'mine',
            'individual': 'mine',
        },
        'delete': {
            'admin': 'mine',        # Nobody deletes someone else's objective
            'manager': 'mine',
            'individual': 'mine',
        },
    },
}
