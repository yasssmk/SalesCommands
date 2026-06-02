# app_modules/ai_pipelines/models/pipeline_run.py
"""
AIPipelineRun — audit record for every LLM pipeline invocation.

One row per call to pipeline.run(). Captures everything needed for
support diagnostics and SOC 2 audit, but NEVER the transcript payload
itself — only an sha256 input_hash. This deliberate design preserves
privacy and bounds storage growth (a long transcript would otherwise
balloon the audit table).

Fields:
  pipeline_type        — which business case ran (AIPipelineType).
  prompt_versions      — JSON dict mapping prompt-name → version tag
                          (e.g. {"pain": "v1", "objective": "v1",
                                  "techstack": "v1"}).
                          Enables prompt-revision audit when
                          debugging extraction quality drift.
  provider             — active provider key at run time
                          ("openai", "claude", ...). Captured even
                          though AIPipelineType implies a default —
                          this column reflects what ACTUALLY ran.
  model_name           — exact model identifier passed to the SDK
                          (e.g. "gpt-4o-mini",
                          "claude-haiku-4-5-20251001"). Captured at
                          run time because pipeline-level overrides
                          are possible.
  temperature          — temperature used for this run. Each
                          pipeline declares its own TEMPERATURE
                          constant — capturing here lets the audit
                          trail verify it did not drift.
  source_activity      — the Activity whose transcript was
                          processed. Nullable for future pipelines
                          that don't have one (e.g. semantic
                          retrieval). SET_NULL on Activity deletion
                          so the audit row survives.
  input_hash           — sha256 hex of the input transcript
                          (64-character lowercase). The transcript
                          itself is NEVER stored — this hash lets
                          support correlate "same input processed
                          twice" without retaining content.
  status               — AIPipelineStatus terminal or in-progress
                          state.
  sub_calls            — JSON list of per-call diagnostic dicts:
                            [
                              {
                                "stage": "pain" | "objective" |
                                          "techstack",
                                "status": "success" | "parse_error"
                                          | "llm_error" | "timeout",
                                "model": "<model>",
                                "tokens": {"input": int,
                                            "output": int},
                                "duration_ms": int,
                                "error": "<string or null>"
                              }
                            ]
  total_tokens_used    — sum of input + output tokens across all
                          sub-calls. Drives cost monitoring and
                          tenant quota tracking.
  total_duration_ms    — wall-clock duration of the orchestrator
                          run.
  error_message        — top-level orchestrator error when status
                          is a terminal failure. MUST NOT contain
                          user payload (transcript fragments /
                          quotes) — only stack summary and provider
                          message. Privacy-sensitive content
                          sanitised by the orchestrator before
                          persistence.
  created_signals_count — number of signals successfully persisted
                          by the run's downstream extractor. Lets
                          the API response surface "we extracted N
                          signals" without re-querying.

Inherited (via ModuleBaseModel + ClientScopeManager.ModelMixin):
  id, client / client_id, created_by, updated_by, created_at,
  updated_at.

Tenant isolation:
  ClientScopeManager.ModelMixin gives client_id. All reads / writes
  through ScopedQuerysetMixin keep runs strictly within their tenant.
  No cross-tenant lookup is possible from the API.

Immutability:
  The permission registry (AI_PIPELINES_REGISTRY) blocks update /
  delete at all tiers. The model itself does NOT enforce this — it
  is an API-level constraint. Direct DB writes via management
  commands remain possible for support workflows (e.g. backfilling
  a missing column).

Cache invalidation:
  None. AIPipelineRun is pure audit — no cluster, no derived list
  endpoint that needs busting. The signals it creates downstream
  trigger their own cache invalidation through SignalManager.create.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager

from ..constants import AIPipelineType, AIPipelineStatus


class AIPipelineRun(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Audit row for an AI pipeline invocation.

    See module docstring for the full field catalogue and design
    rationale (privacy-by-default, immutability, tenant isolation).
    """

    # =========================================================================
    # PIPELINE IDENTITY
    # =========================================================================

    pipeline_type = models.CharField(
        max_length=50,
        choices=AIPipelineType.choices,
        verbose_name=_('Pipeline Type'),
        help_text=_(
            'Identifies which business case produced this run '
            '(e.g. TRANSCRIPT_SIGNALS, NEXT_STEPS).'
        ),
    )

    prompt_versions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Prompt Versions'),
        help_text=_(
            'Mapping prompt-name -> version tag for every prompt used in '
            'this run (e.g. {"pain": "v1", "objective": "v1", '
            '"techstack": "v1"}). Enables prompt-revision audit when '
            'debugging extraction quality drift.'
        ),
    )

    # =========================================================================
    # PROVIDER CONFIGURATION SNAPSHOT
    # =========================================================================

    provider = models.CharField(
        max_length=50,
        verbose_name=_('Provider'),
        help_text=_(
            'Active LLM provider key at run time ("openai", "claude", ...). '
            'Captured even when AIPipelineType implies a default - this '
            'column reflects what actually executed.'
        ),
    )

    model_name = models.CharField(
        max_length=100,
        verbose_name=_('Model'),
        help_text=_(
            'Exact model identifier passed to the SDK '
            '(e.g. "gpt-4o-mini", "claude-haiku-4-5-20251001"). '
            'Captured per run because pipeline-level overrides are '
            'possible.'
        ),
    )

    temperature = models.FloatField(
        verbose_name=_('Temperature'),
        help_text=_(
            'Temperature used for this run. Each pipeline declares its '
            'own TEMPERATURE constant - capturing here lets the audit '
            'trail verify it did not drift.'
        ),
    )

    # =========================================================================
    # INPUT REFERENCE - privacy-preserving
    # =========================================================================

    source_activity = models.ForeignKey(
        'module_activities.Activity',
        on_delete=models.SET_NULL,
        related_name='ai_pipeline_runs',
        null=True,
        blank=True,
        verbose_name=_('Source Activity'),
        help_text=_(
            'Activity whose transcript was processed. Nullable to '
            'support future pipelines that operate without one '
            '(semantic retrieval, batch reprocessing). SET_NULL on '
            'Activity deletion so the audit row survives.'
        ),
    )

    input_hash = models.CharField(
        max_length=64,
        verbose_name=_('Input Hash (sha256)'),
        help_text=_(
            'sha256 hex of the input transcript (64-character '
            'lowercase). The transcript itself is NEVER stored - this '
            'hash lets support correlate "same input processed twice" '
            'without retaining content.'
        ),
    )

    # =========================================================================
    # LIFECYCLE STATE
    # =========================================================================

    status = models.CharField(
        max_length=20,
        choices=AIPipelineStatus.choices,
        default=AIPipelineStatus.RUNNING,
        verbose_name=_('Status'),
        help_text=_(
            'RUNNING at orchestrator entry; SUCCESS / PARTIAL / '
            'PARSE_ERROR / LLM_ERROR / TIMEOUT at finalisation.'
        ),
    )

    # =========================================================================
    # PER-CALL DIAGNOSTICS
    # =========================================================================

    sub_calls = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Sub-call Diagnostics'),
        help_text=_(
            'List of per-call diagnostic dicts: stage, status, model, '
            'token counts, duration, error message. Surface for '
            'support review when a run lands in PARTIAL / PARSE_ERROR / '
            'LLM_ERROR / TIMEOUT.'
        ),
    )

    total_tokens_used = models.IntegerField(
        default=0,
        verbose_name=_('Total Tokens Used'),
        help_text=_(
            'Sum of input + output tokens across all sub-calls. Drives '
            'cost monitoring and tenant quota tracking.'
        ),
    )

    total_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Total Duration (ms)'),
        help_text=_('Wall-clock duration of the orchestrator run.'),
    )

    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message'),
        help_text=_(
            'Top-level orchestrator error when status is a terminal '
            'failure. MUST NOT contain user payload (transcript '
            'fragments, quotes) - only stack summary and provider '
            'message. Privacy-sensitive content sanitised by the '
            'orchestrator before persistence.'
        ),
    )

    # =========================================================================
    # OUTCOME SUMMARY
    # =========================================================================

    created_signals_count = models.IntegerField(
        default=0,
        verbose_name=_('Created Signals Count'),
        help_text=_(
            'Number of signals successfully persisted by the run\'s '
            'downstream extractor. Lets the API response surface '
            '"we extracted N signals" without re-querying.'
        ),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_ai_pipelines_run'
        verbose_name = _('AI Pipeline Run')
        verbose_name_plural = _('AI Pipeline Runs')
        ordering = ['-created_at']
        indexes = [
            # "Show my recent runs" - drives the audit dashboard and
            # per-user history view. Uses client_id (UUIDField on
            # ClientScopeManager.ModelMixin) — NOT 'client'. The mixin
            # carries the tenant via a flat UUID column, not a FK.
            models.Index(
                fields=['client_id', 'created_by', '-created_at'],
                name='aipipe_client_user_date_idx',
            ),
            # "Show all failed transcript extractions" - drives support
            # triage and quality monitoring.
            models.Index(
                fields=['pipeline_type', 'status'],
                name='aipipe_type_status_idx',
            ),
            # "Same input replayed" detection - support diagnostics
            # when a rep retries against an identical transcript.
            models.Index(
                fields=['input_hash'],
                name='aipipe_input_hash_idx',
            ),
        ]

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"AIPipelineRun | "
            f"{self.get_pipeline_type_display()} | "
            f"{self.get_status_display()} | "
            f"{self.created_at:%Y-%m-%d %H:%M}"
        )