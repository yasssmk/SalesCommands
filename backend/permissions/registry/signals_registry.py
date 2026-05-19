# permissions/registry/signals_registry.py
"""
Permissions registry for the Signals module.

The Signals module is the operational core of the post-call workflow:
sales reps capture, validate, and refine PainSignal, ObjectiveSignal,
TechStackSignal, and PainImpact records on accounts. All tiers (admin,
manager, individual) participate fully in this loop — collaboration is
the expected mode, not the exception (a senior rep may validate a
PENDING signal a junior rep extracted, a manager may correct a
misclassified pain, etc.).

Permission matrix:

    +----------+--------+---------+------------+
    | Action   | admin  | manager | individual |
    +----------+--------+---------+------------+
    | create   | client | client  | client     |
    | read     | client | client  | client     |
    | update   | client | client  | client     |
    | delete   | client | client  | client     |
    +----------+--------+---------+------------+

Covered ViewSets (all declare `module = 'signals'`):
  * PainSignalViewSet
  * ObjectiveSignalViewSet
  * TechStackSignalViewSet
  * PainImpactViewSet
  * SignalClusterListView / DetailView / ArchiveView / UnarchiveView
  * SignalChoicesView (auth-only — JWT presence is sufficient, no
    scope check applied)

Custom actions on the ViewSets:
  * validate / reject — declared via `action_policies` on
    BaseSignalViewSet (CRUD: 'update', scope: 'client').
  * cluster archive / unarchive — declared via the standalone
    cluster APIViews' permission_classes / action_policies.

  Neither is mirrored here; the registry exposes only the four
  standard CRUD actions. Action-level enforcement compounds with the
  registry: a tier needs both the matching CRUD scope here AND the
  declared action policy on the view.

Notes on scope choices:

  * All CRUD = `client` for all tiers
        Signals are operational records that flow across the team.
        Restricting at the tier level would block validation chains,
        manager corrections, and the post-call review loop that the
        product is built around. Inter-rep boundaries — when ever
        needed — are handled by `OwnerScopeMixin` and the ownership
        declaration in `permissions/ownership.py`, not at the
        registry level.

  * No 'team' / 'mine' scopes used
        The signals UX (Activity workspace, Account workspace,
        Cluster drill-down) is built around tenant-wide visibility.
        Narrowing to team or mine would break the workflow. Tenant
        isolation is guaranteed by `ScopedPermission` regardless of
        the action scope declared here.

OWNERSHIP_MAP coupling:

    The `signals` entry in `permissions/ownership.py` (A.10) declares
    ownership_type = 'none' and only `client_account_fk` is set. This
    makes ScopedQuerysetMixin filter strictly by tenant for all tiers,
    consistent with the `client` matrix above. The same applies to the
    PainImpact and SignalCluster surfaces (sharing the `signals`
    module label).
"""

from typing import Dict, Literal


# ============================================================================
# TYPE ALIASES
# ============================================================================

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]


# ============================================================================
# SIGNALS REGISTRY
# ============================================================================

SIGNALS_REGISTRY: Dict[str, ModulePermissions] = {

    # ========================================================================
    # SIGNALS MODULE
    # Covers PainSignal, ObjectiveSignal, TechStackSignal, PainImpact,
    # and SignalCluster surfaces — all declaring module='signals' on
    # their ViewSets / APIViews.
    # Ownership: none (tenant-wide visibility for the operational loop).
    # ========================================================================
    'signals': {
        'create': {
            'admin':      'client',
            'manager':    'client',
            'individual': 'client',
        },
        'read': {
            'admin':      'client',
            'manager':    'client',
            'individual': 'client',
        },
        'update': {
            'admin':      'client',
            'manager':    'client',
            'individual': 'client',
        },
        'delete': {
            'admin':      'client',
            'manager':    'client',
            'individual': 'client',
        },
    },

}