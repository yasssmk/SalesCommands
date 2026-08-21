# app_modules/bi/cache.py
"""
BI cache layer — wraps compute.run() with the repo's EXISTING cache utilities.

Nothing here is new caching machinery: it reuses core/cache_utils.py verbatim
(the same primitives the campaign dashboard uses):

- build_drf_cache_key(namespace, client_id, user_id, perm_version, extra,
  tag_namespace)  -> the tenant/user/perm/tag-versioned key.
- cache_get_set(key, producer, ttl, tag)  -> Redis get-or-set with anti-
  stampede lock; graceful file-cache fallback.
- get_permissions_version() / get_tag_version()  -> perm + tag versioning.

Key composition (so two different users / scopes / periods never collide):
    crm:v1:c<client_id>:u<user_id>:p<perm_version>:<kpi.key>:tv<tag_ver>:x<hash>
where the hashed `extra` encodes  scope | period | the versions of ALL of the
KPI's cache_tags. Encoding every cache_tag version means a bump of ANY of them
(via invalidate_tag in palier 1e) changes the key -> the entry goes stale,
reusing the existing tag-version invalidation exactly.

Non-Redis backends: we bypass the cache and compute fresh (same convention as
the campaign dashboard, campaign_views.py) — tag-version invalidation is a
Redis feature, so we don't serve potentially-stale file-cache entries.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.cache_utils import (
    _is_redis_backend,
    build_drf_cache_key,
    build_tag_signature,
    cache_get_set,
    get_permissions_version,
)

from . import compute
from .registry import KPIDefinition
from .types import KPIResult, Period

logger = logging.getLogger(__name__)

# Live-dashboard TTL, matching the campaign dashboard (30s).
DEFAULT_TTL_SECONDS = 30


def _period_token(period: Optional[Period]) -> str:
    if period is None:
        return 'none'
    return f"{period.start}:{period.end}"


def _params_token(params: Optional[dict]) -> str:
    if not params:
        return 'none'
    return ",".join(f"{k}={params[k]}" for k in sorted(params))


def build_kpi_cache_key(definition: KPIDefinition, auth_ctx, scope: str,
                        period: Optional[Period],
                        params: Optional[dict] = None) -> str:
    """Build the cache key for a (KPI, tenant, user, scope, period, params).

    Reuses build_drf_cache_key. `extra` folds scope + period + params + the
    versions of every cache_tag so any tag bump invalidates the entry, and two
    different parameterizations (e.g. two territory_ids) never collide.
    """
    client_id = auth_ctx.client_id
    primary_tag = definition.cache_tags[0] if definition.cache_tags else None

    # Version signature across ALL cache_tags (not just the primary), so a bump
    # of any of them changes the key. Same helper the campaign read caches use.
    tag_sig = build_tag_signature(client_id, definition.cache_tags)
    extra = (
        f"scope={scope}|period={_period_token(period)}"
        f"|params={_params_token(params)}|tags={tag_sig}"
    )

    return build_drf_cache_key(
        namespace=definition.key,
        client_id=client_id,
        user_id=auth_ctx.user_id,
        perm_version=get_permissions_version(),
        extra=extra,
        tag_namespace=primary_tag,
    )


def cached_run(definition: KPIDefinition, auth_ctx, scope: str,
               period: Optional[Period] = None,
               ttl: int = DEFAULT_TTL_SECONDS,
               params: Optional[dict] = None) -> KPIResult:
    """Return the KPI result, from cache when warm, otherwise computing it.

    The producer is compute.run() from palier 1c. On non-Redis backends we
    bypass the cache and compute fresh.
    """
    def producer() -> KPIResult:
        return compute.run(definition, auth_ctx, scope, period, params)

    # Non-Redis: bypass (tag-version invalidation is Redis-only).
    if not _is_redis_backend():
        return producer()

    key = build_kpi_cache_key(definition, auth_ctx, scope, period, params)
    primary_tag = definition.cache_tags[0] if definition.cache_tags else definition.key
    return cache_get_set(
        key=key,
        producer=producer,
        ttl=ttl,
        tag=(auth_ctx.client_id, primary_tag),
    )
