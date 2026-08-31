// frontend/src/hooks/useDCAllSignals.js

import { useMemo, useCallback } from "react";
import { useGetSignalsByAccount } from "api/signals/signals";

const QUALIFICATION_TYPES = ["pain", "objective", "impact"];
const ALL_TYPES = [
  ...QUALIFICATION_TYPES,
  "tech-stack",
  "blockers",
  "next-steps",
  "people",
  "constraints",
  "competitors",
];

/**
 * Fetch all 8 signal types for a decision cycle in parallel via SWR.
 *
 * Mirrors useActivityAllSignals but scoped by decision_cycle filter
 * (direct FK on BaseSignal.decision_cycle_id) instead of source_activity.
 *
 * @param {string|null} accountId - Account UUID (required for the query)
 * @param {string|null} cycleId - Decision Cycle UUID
 * @returns {Object} { signalsByType, qualificationSignals, techStackSignals,
 *                     blockerSignals, nextStepSignals, peopleSignals,
 *                     constraintSignals, allSignals, loading, error, mutateAll }
 */
export default function useDCAllSignals(accountId, cycleId) {
  const filters = useMemo(
    () => (cycleId ? { decision_cycle_id: cycleId } : {}),
    [cycleId],
  );

  const opts = useMemo(
    () => ({ filters, pageSize: 200 }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(filters)],
  );

  const pain = useGetSignalsByAccount(accountId, "pain", opts);
  const objective = useGetSignalsByAccount(accountId, "objective", opts);
  const impact = useGetSignalsByAccount(accountId, "impact", opts);
  const techStack = useGetSignalsByAccount(accountId, "tech-stack", opts);
  const blockers = useGetSignalsByAccount(accountId, "blockers", opts);
  const nextSteps = useGetSignalsByAccount(accountId, "next-steps", opts);
  const people = useGetSignalsByAccount(accountId, "people", opts);
  const constraints = useGetSignalsByAccount(accountId, "constraints", opts);
  const competitors = useGetSignalsByAccount(accountId, "competitors", opts);

  const signalsByType = useMemo(
    () => ({
      pain: pain.signals,
      objective: objective.signals,
      impact: impact.signals,
      "tech-stack": techStack.signals,
      blockers: blockers.signals,
      "next-steps": nextSteps.signals,
      people: people.signals,
      constraints: constraints.signals,
      competitors: competitors.signals,
    }),
    [
      pain.signals,
      objective.signals,
      impact.signals,
      techStack.signals,
      blockers.signals,
      nextSteps.signals,
      people.signals,
      constraints.signals,
      competitors.signals,
    ],
  );

  const qualificationSignals = useMemo(
    () => [
      ...pain.signals.map((s) => ({ ...s, _signalType: "pain" })),
      ...objective.signals.map((s) => ({ ...s, _signalType: "objective" })),
      ...impact.signals.map((s) => ({ ...s, _signalType: "impact" })),
    ],
    [pain.signals, objective.signals, impact.signals],
  );

  const techStackSignals = useMemo(
    () => techStack.signals.map((s) => ({ ...s, _signalType: "tech-stack" })),
    [techStack.signals],
  );

  const blockerSignals = useMemo(
    () => blockers.signals.map((s) => ({ ...s, _signalType: "blockers" })),
    [blockers.signals],
  );

  const nextStepSignals = useMemo(
    () => nextSteps.signals.map((s) => ({ ...s, _signalType: "next-steps" })),
    [nextSteps.signals],
  );

  const peopleSignals = useMemo(
    () => people.signals.map((s) => ({ ...s, _signalType: "people" })),
    [people.signals],
  );

  const constraintSignals = useMemo(
    () => constraints.signals.map((s) => ({ ...s, _signalType: "constraints" })),
    [constraints.signals],
  );

  const competitorSignals = useMemo(
    () => competitors.signals.map((s) => ({ ...s, _signalType: "competitors" })),
    [competitors.signals],
  );

  const allSignals = useMemo(
    () => [
      ...qualificationSignals,
      ...techStackSignals,
      ...blockerSignals,
      ...nextStepSignals,
      ...peopleSignals,
      ...constraintSignals,
      ...competitorSignals,
    ],
    [
      qualificationSignals,
      techStackSignals,
      blockerSignals,
      nextStepSignals,
      peopleSignals,
      constraintSignals,
      competitorSignals,
    ],
  );

  const loading =
    pain.signalsLoading ||
    objective.signalsLoading ||
    impact.signalsLoading ||
    techStack.signalsLoading ||
    blockers.signalsLoading ||
    nextSteps.signalsLoading ||
    people.signalsLoading ||
    constraints.signalsLoading ||
    competitors.signalsLoading;

  const error =
    pain.signalsError ||
    objective.signalsError ||
    impact.signalsError ||
    techStack.signalsError ||
    blockers.signalsError ||
    nextSteps.signalsError ||
    people.signalsError ||
    constraints.signalsError ||
    competitors.signalsError;

  const mutateAll = useCallback(() => {
    pain.mutateSignals();
    objective.mutateSignals();
    impact.mutateSignals();
    techStack.mutateSignals();
    blockers.mutateSignals();
    nextSteps.mutateSignals();
    people.mutateSignals();
    constraints.mutateSignals();
    competitors.mutateSignals();
  }, [
    pain.mutateSignals,
    objective.mutateSignals,
    impact.mutateSignals,
    techStack.mutateSignals,
    blockers.mutateSignals,
    nextSteps.mutateSignals,
    people.mutateSignals,
    constraints.mutateSignals,
    competitors.mutateSignals,
  ]);

  return {
    signalsByType,
    qualificationSignals,
    techStackSignals,
    blockerSignals,
    nextStepSignals,
    peopleSignals,
    constraintSignals,
    competitorSignals,
    allSignals,
    loading,
    error,
    mutateAll,
  };
}

export { QUALIFICATION_TYPES, ALL_TYPES };
