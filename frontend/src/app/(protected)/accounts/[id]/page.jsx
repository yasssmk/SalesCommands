// src/app/(protected)/accounts/[id]/page.jsx

import AccountWorkspacePage from 'views/accounts/workspace';

// ==============================|| ACCOUNT WORKSPACE PAGE ||============================== //

/**
 * Next.js App Router page component for Account Workspace
 * 
 * Dynamic route that displays account details with tabs:
 * - Overview
 * - Decision Cycle
 * - Activities
 * - Contacts
 * - Signals (flat list + the grouped Qualification synthesis via a toggle)
 *
 * Protected by AuthGuard (via layout)
 */
export default function AccountWorkspaceRoute() {
  return <AccountWorkspacePage />;
}