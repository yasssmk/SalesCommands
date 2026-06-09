// frontend/src/hooks/useActivityAllSignals.js

import { useMemo, useCallback } from "react";
import { useGetSignalsByActivity } from "api/signals/signals";

const QUALIFICATION_TYPES = ["pain", "objective", "impact"];
const ALL_TYPES = [...QUALIFICATION_TYPES, "blockers", "next-steps"];

/**
 * Fetch all 6 signal types for an activity in parallel via SWR.
 *
 * @param {string|null} activityId - Activity UUID
 * @returns {Object} { signalsByType, qualificationSignals, blockerSignals,
 *                     nextStepSignals, allSignals, loading, error, mutateAll }
 */
export default function useActivityAllSignals(activityId) {
  const pain = useGetSignalsByActivity(activityId, "pain");
  const objective = useGetSignalsByActivity(activityId, "objective");
  const impact = useGetSignalsByActivity(activityId, "impact");
  const techStack = useGetSignalsByActivity(activityId, "tech-stack");
  const blockers = useGetSignalsByActivity(activityId, "blockers");
  const nextSteps = useGetSignalsByActivity(activityId, "next-steps");

  const signalsByType = useMemo(
    () => ({
      pain: pain.signals,
      objective: objective.signals,
      impact: impact.signals,
      "tech-stack": techStack.signals,
      blockers: blockers.signals,
      "next-steps": nextSteps.signals,
    }),
    [
      pain.signals,
      objective.signals,
      impact.signals,
      techStack.signals,
      blockers.signals,
      nextSteps.signals,
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

  const allSignals = useMemo(
    () => [...qualificationSignals, ...techStackSignals, ...blockerSignals, ...nextStepSignals],
    [qualificationSignals, techStackSignals, blockerSignals, nextStepSignals],
  );

  const loading =
    pain.signalsLoading ||
    objective.signalsLoading ||
    impact.signalsLoading ||
    techStack.signalsLoading ||
    blockers.signalsLoading ||
    nextSteps.signalsLoading;

  const error =
    pain.signalsError ||
    objective.signalsError ||
    impact.signalsError ||
    techStack.signalsError ||
    blockers.signalsError ||
    nextSteps.signalsError;

  const mutateAll = useCallback(() => {
    pain.mutateSignals();
    objective.mutateSignals();
    impact.mutateSignals();
    techStack.mutateSignals();
    blockers.mutateSignals();
    nextSteps.mutateSignals();
  }, [
    pain.mutateSignals,
    objective.mutateSignals,
    impact.mutateSignals,
    techStack.mutateSignals,
    blockers.mutateSignals,
    nextSteps.mutateSignals,
  ]);

  return {
    signalsByType,
    qualificationSignals,
    techStackSignals,
    blockerSignals,
    nextStepSignals,
    allSignals,
    loading,
    error,
    mutateAll,
  };
}

export { QUALIFICATION_TYPES, ALL_TYPES };
