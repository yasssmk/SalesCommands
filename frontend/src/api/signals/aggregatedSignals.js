// frontend/src/api/signals/aggregatedSignals.js

"use client";

import useSWR from "swr";
import { useMemo } from "react";

import { useAuth } from "hooks/useAuth";
import { tenantKey } from "api/_swr";
import { isValidUUID } from "utils/validators";

const AGGREGATED_URL = "/module-signals/all/";

/**
 * Build the query string for GET /module-signals/all/.
 *
 * Exactly one scope key (account_id | decision_cycle_id | activity_id) is
 * required; optional status, repeatable signal_type, ordering, and the
 * standard page / page_size.
 */
function buildUrl({ scope, statuses, signalTypes, ordering, page, pageSize }) {
  const q = new URLSearchParams();
  q.append(scope.key, scope.id);
  (statuses || []).forEach((s) => q.append("status", s));
  (signalTypes || []).forEach((t) => q.append("signal_type", t));
  if (ordering) q.append("ordering", ordering);
  q.append("page", String(page));
  q.append("page_size", String(pageSize));
  return `${AGGREGATED_URL}?${q.toString()}`;
}

/**
 * useAggregatedSignals — one SWR call to the aggregated endpoint returning a
 * single paginated, mixed, server-sorted list of all signal types for one
 * scope. Replaces the per-type client fan-out on the flat views.
 *
 * Each item is tagged with `_signalType` (copied from the endpoint's
 * `signal_type`) so the existing SignalsFlatView / SignalLine consume it
 * unchanged.
 *
 * @param {Object} args
 * @param {string} [args.accountId]        scope: account
 * @param {string} [args.decisionCycleId]  scope: decision cycle
 * @param {string} [args.activityId]       scope: source activity
 * @param {string[]} [args.statuses]       restrict to these statuses
 * @param {string[]} [args.signalTypes]    restrict to these frontend slugs
 * @param {string} [args.ordering]         date-desc | date-asc | status | type | theme
 * @param {number} [args.page=1]
 * @param {number} [args.pageSize=20]
 */
export default function useAggregatedSignals({
  accountId,
  decisionCycleId,
  activityId,
  statuses,
  signalTypes,
  ordering,
  page = 1,
  pageSize = 20,
} = {}) {
  const { tenantId } = useAuth();

  // Exactly one valid scope; otherwise the hook is disabled (null key).
  let scope = null;
  if (accountId && isValidUUID(accountId)) {
    scope = { key: "account_id", id: accountId };
  } else if (decisionCycleId && isValidUUID(decisionCycleId)) {
    scope = { key: "decision_cycle_id", id: decisionCycleId };
  } else if (activityId && isValidUUID(activityId)) {
    scope = { key: "activity_id", id: activityId };
  }

  const scopeKey = scope?.key ?? null;
  const scopeId = scope?.id ?? null;
  const typesKey = JSON.stringify(signalTypes ?? null);
  const statusKey = JSON.stringify(statuses ?? null);

  const url = useMemo(
    () =>
      scope
        ? buildUrl({ scope, statuses, signalTypes, ordering, page, pageSize })
        : null,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scopeKey, scopeId, statusKey, typesKey, ordering, page, pageSize],
  );

  const swrKey = tenantKey(url, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
    keepPreviousData: true,
  });

  return useMemo(() => {
    const raw = data?.data?.results ?? data?.results ?? [];
    const count = data?.data?.count ?? data?.count ?? 0;
    return {
      // Tag with _signalType so SignalsFlatView / SignalLine work unchanged.
      signals: raw.map((s) => ({ ...s, _signalType: s.signal_type })),
      count,
      next: data?.data?.next ?? data?.next ?? null,
      previous: data?.data?.previous ?? data?.previous ?? null,
      pageCount: Math.max(1, Math.ceil(count / pageSize)),
      loading: isLoading,
      validating: isValidating,
      error,
      mutate,
    };
  }, [data, isLoading, isValidating, error, mutate, pageSize]);
}
