# permissions/registry/tech_catalog_registry.py
"""
Permissions registry for the TechCatalog module.

The TechCatalog is a tenant-level master catalog of technologies (Salesforce,
HubSpot, etc.) used by the sales organization. It is administered exclusively
by tenant admins, but read access is open to all authenticated users so that
sales reps can consume it through AsyncTechCatalogSelect when capturing
TechStackSignals (Sprint TechStack-B and beyond).

Permission matrix:

    +----------+-------+---------+------------+
    | Action   | admin | manager | individual |
    +----------+-------+---------+------------+
    | create   | client| none    | none       |
    | read     | client| client  | client     |
    | update   | client| none    | none       |
    | delete   | client| none    | none       |
    +----------+-------+---------+------------+

Custom actions on the ViewSet (validate, deprecate, merge) are admin-only
and routed through `action_policies` on the TechCatalogViewSet itself —
they are NOT declared here. The registry only carries the four standard
CRUD actions; custom actions need policy-level enforcement (tier='admin')
and are configured at the view layer.

Notes on scope choices:

  * `read = client` for ALL tiers
        Reps must see the catalog to pick from it in their flows. The
        catalog is non-sensitive (vendor names, public categorization)
        and contains no per-record ownership semantics — there is no
        "team scope" or "mine scope" interpretation that would make
        sense for a tenant-wide reference list.

  * `create / update / delete = none` for non-admin
        The catalog is a curated reference shared by the tenant. Allowing
        reps to mutate it directly would erode quality. The `DRAFT`
        workflow exists so that reps can SUGGEST entries (in Sprint
        TechStack-B, via inline-creation in TechStackSignal forms) which
        admins then review and validate. Until that flow ships, only
        admins can write.

OWNERSHIP_MAP coupling:

    The `tech_catalog` entry in `permissions/ownership.py` declares
    ownership_type = 'none' and only `client_account_fk` is set. This
    makes ScopedQuerysetMixin filter strictly by tenant for all tiers,
    consistent with the `read = client` matrix above.
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
# TECH_CATALOG REGISTRY
# ============================================================================

TECH_CATALOG_REGISTRY: Dict[str, ModulePermissions] = {

    # ========================================================================
    # TECH_CATALOG MODULE
    # Ownership: none (tenant-level reference catalog)
    # Admin-only writes; tenant-wide reads.
    # Custom actions (validate / deprecate / merge) enforced via
    # action_policies on the ViewSet, not in this registry.
    # ========================================================================
    'tech_catalog': {
        'create': {
            'admin':      'client',  # Admins create catalog entries
            'manager':    'none',    # Managers cannot create
            'individual': 'none',    # Reps cannot create directly
        },
        'read': {
            'admin':      'client',  # Admin sees full tenant catalog
            'manager':    'client',  # Manager sees full tenant catalog
            'individual': 'client',  # Reps consume catalog via AsyncTechCatalogSelect
        },
        'update': {
            'admin':      'client',  # Admins edit any entry
            'manager':    'none',    # Managers cannot edit
            'individual': 'none',    # Reps cannot edit
        },
        'delete': {
            'admin':      'client',  # Admins delete (rare — DEPRECATED preferred)
            'manager':    'none',    # Managers cannot delete
            'individual': 'none',    # Reps cannot delete
        },
    },

}