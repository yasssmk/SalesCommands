// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepTabs.jsx
/**
 * Decision Step Tabs — Config only.
 *
 * Tab rendering is handled by WorkspaceLayout.
 * This file exports tab definitions consumed by the workspace page.
 */

export const DECISION_STEP_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'activities', label: 'Activities' },
  { id: 'contacts', label: 'Contacts' },
  { id: 'signals', label: 'Signals', disabled: true },
  { id: 'ai-prep', label: 'AI Preparation', disabled: true }
];

export const DEFAULT_TAB = 'overview';