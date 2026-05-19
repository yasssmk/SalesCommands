# backend/core/timeout_conventions.py
"""
Timeout & Operation Tier Conventions for SalesCommands.

================================================================================
SINGLE SOURCE OF TRUTH for how the platform classifies API operations
by latency origin and applies coherent timeout, idempotency, polling,
and UX rules across the stack.
================================================================================

Why this file exists
--------------------
Different API operations have different latency origins:
    - Internal: DB queries, mutations, bulk writes -> we own the latency,
                fail fast is good (10-60s budgets).
    - External: 3rd-party API calls (LLM, payment, webhooks) -> we depend
                on someone else's SLA, must accept long waits and pay
                for retries, double-spend protection is critical.

Treating both the same way is a category error: a 60s timeout that's a
"failsafe" for an internal bulk op is an "everyday occurrence" for a
3-LLM-call extraction pipeline. This file defines the convention to
keep that distinction explicit and applied uniformly.

Whenever a new endpoint is added, classify it against the tier table
below and apply the matching rules. Whenever an existing endpoint
changes its latency profile (e.g. starts hitting a 3rd party), reclassify
it and update its callers.


Operation tiers
---------------
T0 - Internal sync read         e.g. GET /accounts/{id}/
                                Latency: <500ms typical
                                Failure cost: cheap, retry trivially

T1 - Internal sync write        e.g. PATCH /contacts/{id}/
                                Latency: <2s typical
                                Failure cost: maybe a stale row, fix on retry

T2 - Internal bulk write        e.g. POST /accounts/bulk-create/
                                Latency: 5-60s typical
                                Failure cost: partial state in DB, idempotency required

T3 - External single call       e.g. 1 LLM call, 1 payment authorization
                                Latency: 1-30s typical
                                Failure cost: 3rd party money spent, idempotency required

T4 - External pipeline          e.g. chained LLM extraction (THIS SPRINT),
                                multi-step provider workflow
                                Latency: 10-180s typical
                                Failure cost: 3rd party money spent N times if not deduped
                                              + UX complexity (long wait)


Rule matrix
-----------
    Rule                          T0  T1  T2  T3  T4
    Axios profile (frontend)      crit/wgt mut bulk bulk bulk
    Gunicorn min --timeout (s)*   12  12  12  12  12       (* see GUNICORN section)
    Idempotency required          -   -   yes yes yes
    Idempotency key strategy      -   -   random random DETERMINISTIC
    Polling fallback required     -   -   yes yes YES (mandatory)
    Backend DB dedup layer 2      -   -   -   opt YES
    UX pattern                    inline btn  modal modal PERSISTENT WIZARD


The 6 hard rules
----------------
R1 - COST GATE (T3/T4):
    No paid 3rd-party call without an Idempotency-Key reaching
    `core.idempotency.start_op()` first. Views that bypass this gate
    are reviewer-blockers.

R2 - SLA CHAIN:
    backend_capacity >= frontend_axios_timeout >= provider_timeout * num_calls
    The shortest link breaks robustness. With uvicorn async workers,
    "backend_capacity" is bounded by --graceful-timeout (deploy SIGTERM
    grace) and thread pool exhaustion, not by --timeout. See GUNICORN
    NOTES below.

R3 - POLLING FALLBACK (T2+):
    Frontend NEVER does a simple try/catch on a POST T2+. Required
    pattern: try -> handleBulkTimeout on isTimeout -> poll /ops/{key}/.
    A network drop without polling = result lost = user retries =
    3rd-party double-spend.

R4 - IDEMPOTENCY KEY STRATEGY:
    T2/T3 -> random UUID auto-injected by axios interceptor.
             Each click = new op, acceptable for low-cost internal ops.
    T4    -> deterministic key. Client computes
             sha256(stable_inputs) and overrides the auto-injection
             with an explicit Idempotency-Key header. Same inputs ->
             same key -> backend replays cached response without
             re-spending tokens.

R5 - UX WAIT PATTERN (T3+):
    Modal/wizard stays open during the whole operation including the
    polling phase. Auto-close on success only. States surfaced to UI:
        submitting -> running -> polling (n/max) ->
            success | dedup_409 | timeout | error
    Cancel = closes UI only (confirmation required). Backend continues
    until completion. User re-entering the flow with the same inputs
    sees cached/in-progress state via the deterministic key.

R6 - BACKEND DEDUP LAYER 2 (T4 only):
    Redis idempotency has IDEMPOTENCY_REDIS_TTL_SECONDS (10 min) TTL.
    Beyond that, fallback to DB-level dedup using the operation's
    business-identity hash (for AI pipeline: AIPipelineRun.input_hash).
    Hit -> 409 Conflict + metadata pointing to the existing run. We
    do NOT attempt to replay the old signals (they may have been
    edited/rejected/deleted post-extraction -- state corruption risk).


================================================================================
"""

# ============================================================================
# OPERATION TIER IDENTIFIERS (use these in view docstrings / annotations)
# ============================================================================

TIER_T0_INTERNAL_SYNC_READ   = 'T0'
TIER_T1_INTERNAL_SYNC_WRITE  = 'T1'
TIER_T2_INTERNAL_BULK        = 'T2'
TIER_T3_EXTERNAL_SINGLE      = 'T3'
TIER_T4_EXTERNAL_PIPELINE    = 'T4'


# ============================================================================
# IDEMPOTENCY
# ============================================================================

# Matches core.idempotency.DEFAULT_TTL. Redefined here as the canonical
# value so callers do not have to import the implementation module.
IDEMPOTENCY_REDIS_TTL_SECONDS = 600  # 10 minutes

# Strategy identifiers (used in docstrings and code annotations)
IDEMPOTENCY_STRATEGY_NONE          = 'none'
IDEMPOTENCY_STRATEGY_RANDOM        = 'random'         # axios auto-injected UUID
IDEMPOTENCY_STRATEGY_DETERMINISTIC = 'deterministic'  # client-computed hash of stable inputs


# ============================================================================
# POLLING
# ============================================================================
# Mirrors frontend `handleBulkTimeout` + `pollOperationStatus` defaults.
# If these change client-side, update the constants here so they stay
# in sync. The server respects the Redis TTL (10 min) regardless --
# these are the client expectations.

POLLING_ENDPOINT_PATTERN     = '/ops/{key}/'  # GET endpoint, see backend/ops/urls.py
POLLING_MAX_ATTEMPTS         = 36              # ~3 minutes at 5-second interval
POLLING_INTERVAL_SECONDS     = 5


# ============================================================================
# AI PIPELINE (T4) -- specifics for the LLM transcript-signals pipeline
# ============================================================================

AI_PIPELINE_TIER                         = TIER_T4_EXTERNAL_PIPELINE
AI_PIPELINE_IDEMPOTENCY_STRATEGY         = IDEMPOTENCY_STRATEGY_DETERMINISTIC
AI_PIPELINE_BACKEND_DB_DEDUP_REQUIRED    = True

# AIPipelineRun statuses that count as "already extracted" for the
# layer-2 DB dedup check. Anything else (PARSE_ERROR, LLM_ERROR,
# TIMEOUT) is treated as "no successful prior extraction" -- we
# allow a fresh retry in that case.
AI_PIPELINE_DEDUP_RUN_STATUSES           = ('SUCCESS', 'PARTIAL')


# ============================================================================
# GUNICORN NOTES (informational -- actual values live in deploy config)
# ============================================================================
# Current production config (Render):
#     gunicorn salescommands.asgi:application
#       -k uvicorn.workers.UvicornWorker
#       --workers ${WEB_CONCURRENCY:-2}
#       --timeout 12
#       --graceful-timeout 12
#       --keep-alive 2
#
# Why --timeout 12 is fine for T4 (10-180s pipeline) under uvicorn:
#   * `-k uvicorn.workers.UvicornWorker` runs each worker as an async
#     event loop.
#   * Django sync views are dispatched to a thread pool via
#     `sync_to_async`. The thread blocks during the LLM call, but the
#     event loop stays free.
#   * The event loop responds to the gunicorn master heartbeat
#     regardless of whether sync view threads are busy. So worker
#     liveness is satisfied -- --timeout 12 is respected.
#   * Conclusion: --timeout = liveness check, NOT per-request budget,
#     for async worker classes.
#
# Why --graceful-timeout 12 is a known T4 deploy-time risk:
#   * On SIGTERM (deploy, autoscale), gunicorn gives in-flight
#     requests --graceful-timeout seconds to finish.
#   * T4 ops typically take 10-90s -> killed mid-call during deploys.
#   * Recovery path: Redis stores the operation in 'running' state
#     until TTL. Polling client sees 'still_running' -> timeout after
#     POLLING_MAX_ATTEMPTS -> can retry. Same deterministic key picks
#     up the (failed-by-kill) state, allowing a clean retry.
#   * Mitigation if deploy frequency justifies:
#     bump --graceful-timeout to GRACEFUL_TIMEOUT_T4_RECOMMENDED.
#     Trade-off: rolling restarts take longer.
GRACEFUL_TIMEOUT_T4_RECOMMENDED = 200  # seconds


# ============================================================================
# FRONTEND CONSTANTS (informational mirror -- single source of truth lives
# in frontend/src/config/auth -> TIMEOUT_PROFILES)
# ============================================================================
# Listed here so backend code reading this convention sees the full
# picture. Do not import; these are documentation.

FRONTEND_AXIOS_PROFILE_FOR_T4 = 'bulk'  # see frontend/src/utils/axiosClient.js
FRONTEND_AXIOS_TIMEOUT_BULK   = 60      # seconds (authConfig.TIMEOUT_PROFILES.BULK)