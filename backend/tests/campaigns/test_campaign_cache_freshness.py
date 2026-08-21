# backend/tests/campaigns/test_campaign_cache_freshness.py
"""
The campaign read caches must go stale when a campaign's NUMBERS change, not
only when its structure does.

THE BUG. The list card, the detail page and the workspace dashboard are cached
server-side (campaign_views.py), keyed via
``build_drf_cache_key(tag_namespace='campaigns')`` — which folds exactly ONE tag
version into the key (core/cache_utils.py:461-504, and its own docstring example
``tv5``). But the values in those payloads come from decision cycles, deal
products, activities and account conversions, and every one of those writes bumps
``decision_cycles`` / ``activities`` / ``accounts`` — never ``campaigns``:

    decision_cycles/views/views.py:267-269   -> decision_cycles, activities, accounts
    decision_cycles/views/deal_product_views.py:144 -> decision_cycles
    activities/signals/cache_invalidation.py:44-46  -> activities, accounts, decision_cycles

So the key did not move, the cached body was served for the full TTL (60s list and
detail, 30s dashboard), and a browser refresh could not help: the staleness is in
Redis, not in the client.

WHY THESE TESTS ASSERT ON THE KEY, NOT ON OBSERVED STALENESS. Both cache layers
BYPASS entirely on a non-Redis backend (campaign_views.py:403, bi/cache.py:105),
so a test that wrote, read and compared values would pass vacuously wherever
Redis is absent — including this suite's own environment. The key is the thing
that has to change, so the key is what is asserted.

They also drive ``increment_tag_version`` rather than ``invalidate_tag``:
``invalidate_tag`` returns early without Redis (cache_utils.py:565-570) and never
touches the local version counter, while ``increment_tag_version`` falls back to
it (:210). ``invalidate_tag`` delegates to it (:573), so this exercises the same
primitive in both environments.

DB: not needed — this is key composition, no query.
"""

import pytest

from core.cache_utils import (
    build_tag_signature,
    get_tag_version,
    increment_tag_version,
)
from app_modules.campaigns.views.campaign_views import (
    CAMPAIGN_CACHE_TAGS,
    build_campaign_cache_key,
)


CLIENT = 'cache-freshness-tenant'
USER = 'user-1'


def _key(namespace='campaigns_list', **kwargs):
    return build_campaign_cache_key(
        namespace=namespace, client_id=CLIENT, user_id=USER, **kwargs,
    )


# The three cached surfaces, with the discriminator each one passes.
SURFACES = [
    ('campaigns_list', {'query_string': 'status=ACTIVE'}),
    ('campaign_detail', {'extra': 'campaign-uuid'}),
    ('campaign_dashboard', {'extra': 'campaign-uuid'}),
]

# The tags whose bump must move the key. 'campaigns' is the structure tag that
# already worked; the other three are the ones the bug ignored.
NUMBER_TAGS = ['decision_cycles', 'activities', 'accounts']


class TestTheKeyMovesWhenTheNumbersCanChange:

    @pytest.mark.parametrize('namespace,kwargs', SURFACES)
    @pytest.mark.parametrize('tag', NUMBER_TAGS)
    def test_bumping_a_number_tag_changes_the_key(self, namespace, kwargs, tag):
        before = _key(namespace, **kwargs)
        increment_tag_version(CLIENT, tag)
        after = _key(namespace, **kwargs)

        assert before != after, f'{namespace} ignored a {tag} bump'

    @pytest.mark.parametrize('namespace,kwargs', SURFACES)
    def test_bumping_the_structure_tag_still_changes_the_key(self, namespace,
                                                             kwargs):
        """Regression: folding the new tags must not cost the one that already
        worked. A campaign rename still busts every surface."""
        before = _key(namespace, **kwargs)
        increment_tag_version(CLIENT, 'campaigns')
        after = _key(namespace, **kwargs)

        assert before != after

    def test_every_tag_the_payload_depends_on_is_declared(self):
        """The declaration is the contract: a future writer adding a source to a
        campaign payload has one list to extend, and this names the four."""
        assert set(CAMPAIGN_CACHE_TAGS) == {
            'campaigns', 'decision_cycles', 'activities', 'accounts',
        }

    @pytest.mark.parametrize('tag', ['campaigns'] + NUMBER_TAGS)
    def test_the_signature_carries_each_tag_version_verbatim(self, tag):
        """Guards the guard: the assertions above would also pass if the key
        merely embedded a timestamp or a random salt. The folded signature must
        carry each tag's ACTUAL current version — which is what makes the key
        stable between bumps and different across one."""
        version = get_tag_version(CLIENT, tag)

        assert f'{tag}={version}' in build_tag_signature(CLIENT,
                                                         CAMPAIGN_CACHE_TAGS)

    def test_two_reads_with_no_write_in_between_hit_the_same_key(self):
        """The other half of correctness: the key must be STABLE, or the cache
        would never hit and every campaign page would recompute."""
        assert _key() == _key()


class TestTheOldSingleTagKeyWasTheBug:
    """Pins WHY the fold is needed, so the fix cannot be quietly reverted.

    This builds the key the way the three views built it before — one
    ``tag_namespace``, nothing folded — and shows a decision_cycles bump leaves
    it untouched. That is the stale card, reproduced at the level it actually
    broke.
    """

    def test_a_single_tag_namespace_key_ignores_a_decision_cycles_bump(self):
        from core.cache_utils import build_drf_cache_key

        def old_key():
            return build_drf_cache_key(
                namespace='campaigns_list', client_id=CLIENT, user_id=USER,
                perm_version='v1', query_string='status=ACTIVE',
                tag_namespace='campaigns',
            )

        before = old_key()
        increment_tag_version(CLIENT, 'decision_cycles')

        assert old_key() == before          # the stale card, in one assertion

    def test_the_new_key_does_not(self):
        before = _key(query_string='status=ACTIVE')
        increment_tag_version(CLIENT, 'decision_cycles')

        assert _key(query_string='status=ACTIVE') != before
