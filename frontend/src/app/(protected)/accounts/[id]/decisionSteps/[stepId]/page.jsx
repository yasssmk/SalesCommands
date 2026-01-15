// frontend/src/app/(protected)/accounts/[id]/decisionSteps/[stepId]/page.jsx


import DecisionStepWorkspacePage from 'views/accounts/decisionSteps';

// ==============================|| DECISION STEP WORKSPACE PAGE ||============================== //

/**
 * Next.js App Router page component for Decision Step Workspace
 * 
 * Dynamic route: /accounts/[accountId]/steps/[stepId]
 * 
 * Displays a full-page Decision Step detail with tabs:
 * - Overview (step details, completeness score, manager notes)
 * - Activities (linked activities list with create action)
 * - Contacts (related contacts)
 * - Signals (stub - Phase 3)
 * - AI Preparation (stub - Phase 3)
 * 
 * Protected by AuthGuard (via parent layout)
 * 
 * @see StepWorkspacePage - Main orchestrator component
 */
export default function StepWorkspaceRoute() {
  return <DecisionStepWorkspacePage />;
}
