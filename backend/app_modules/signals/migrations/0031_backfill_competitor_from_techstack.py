# Data migration: backfill CompetitorSignal from TechStackSignal.is_competitor.
#
# For every TechStackSignal with is_competitor=True and a non-blank tech_name,
# create a mirror CompetitorSignal (the C of MEDDPICC). This is a DATA-only
# migration -- it performs NO schema change; the CompetitorSignal table and
# columns were created by 0030_competitorsignal.
#
# Frozen mapping (sub-step 3):
#   competitor_name            <- tech_name (stripped)
#   competitor_name_normalized <- derived here (lower + strip + collapse ws),
#                                 the SAME logic as
#                                 CompetitorSignal._normalize_competitor_name.
#                                 The historical model has no save(), so the
#                                 key MUST be computed in the migration.
#   summary                    <- f"Competitor: {tech_name}"
#   source_quote               <- copied (may be NULL)
#   status / confidence / is_inferred / source
#   account_id / decision_cycle_id / source_activity_id / client_id
#   created_by_id / updated_by_id  <- copied as-is
#   campaign_id                <- source_activity.campaign_id when
#                                 source_activity is set, else None (TechStack
#                                 has no campaign column of its own).
#   metadata                   <- {'backfilled_from': 'techstack_is_competitor'}
#                                 (the reversibility marker)
#
# Exclusions: btrim(tech_name) = '' (no name -> no CompetitorSignal), and
# is_competitor=False (never a competitor).
#
# Idempotence: a row is created only when no CompetitorSignal already exists
# with the same (source_activity_id, competitor_name_normalized, client_id).
# Re-running the forward pass creates no duplicates.
#
# Reversible: reverse() deletes exactly the CompetitorSignal rows carrying
# metadata['backfilled_from'] == 'techstack_is_competitor'.

from django.db import migrations


BACKFILL_MARKER = 'techstack_is_competitor'


def _normalize_competitor_name(value):
    """Lower + strip + collapse internal whitespace.

    Copy of CompetitorSignal._normalize_competitor_name -- the concrete
    model's save() is not available on the historical model used here, so the
    normalisation logic is inlined to stay in lock-step with it.
    """
    if not value:
        return ''
    return ' '.join(str(value).lower().split())


def forwards(apps, schema_editor):
    TechStackSignal = apps.get_model('module_signals', 'TechStackSignal')
    CompetitorSignal = apps.get_model('module_signals', 'CompetitorSignal')
    Activity = apps.get_model('module_activities', 'Activity')

    # Cache source_activity -> campaign_id lookups to avoid one query per row.
    campaign_by_activity = {}

    qs = (
        TechStackSignal.objects
        .filter(is_competitor=True)
        .iterator()
    )

    for ts in qs:
        raw_name = ts.tech_name or ''
        name = raw_name.strip()
        if not name:
            # Blank tech_name -> no CompetitorSignal (frozen exclusion).
            continue

        # Defensive: a signal row without its required tenant/account anchor is
        # malformed -- skip rather than raise a bare exception.
        if not ts.client_id or not ts.account_id:
            continue

        normalized = _normalize_competitor_name(name)

        # Idempotence: skip when a mirror already exists for this
        # (source_activity, normalised name, tenant).
        already = CompetitorSignal.objects.filter(
            source_activity_id=ts.source_activity_id,
            competitor_name_normalized=normalized,
            client_id=ts.client_id,
        ).exists()
        if already:
            continue

        # campaign_id follows the source activity (TechStack has no campaign
        # column of its own); None when there is no source activity.
        if ts.source_activity_id is None:
            campaign_id = None
        elif ts.source_activity_id in campaign_by_activity:
            campaign_id = campaign_by_activity[ts.source_activity_id]
        else:
            campaign_id = (
                Activity.objects
                .filter(id=ts.source_activity_id)
                .values_list('campaign_id', flat=True)
                .first()
            )
            campaign_by_activity[ts.source_activity_id] = campaign_id

        CompetitorSignal.objects.create(
            account_id=ts.account_id,
            client_id=ts.client_id,
            source_activity_id=ts.source_activity_id,
            decision_cycle_id=ts.decision_cycle_id,
            campaign_id=campaign_id,
            competitor_name=name,
            competitor_name_normalized=normalized,
            summary=f'Competitor: {name}',
            source_quote=ts.source_quote,
            confidence=ts.confidence,
            is_inferred=ts.is_inferred,
            source=ts.source,
            status=ts.status,
            created_by_id=ts.created_by_id,
            updated_by_id=ts.updated_by_id,
            metadata={'backfilled_from': BACKFILL_MARKER},
        )


def reverse(apps, schema_editor):
    CompetitorSignal = apps.get_model('module_signals', 'CompetitorSignal')
    # Delete exactly the rows this migration created (marker-scoped).
    CompetitorSignal.objects.filter(
        metadata__backfilled_from=BACKFILL_MARKER,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('module_signals', '0030_competitorsignal'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
