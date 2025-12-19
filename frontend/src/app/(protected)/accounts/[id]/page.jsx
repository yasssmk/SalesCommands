// src/app/(protected)/accounts/[id]/page.jsx

import AccountWorkspacePage from 'views/accounts/workspace';

// ==============================|| ACCOUNT WORKSPACE PAGE ||============================== //

/**
 * Next.js App Router page component for Account Workspace
 * 
 * Dynamic route that displays account details with tabs:
 * - Summary
 * - Qualification
 * - Buying Process
 * - Activities
 * - Contacts
 * - Signals
 * 
 * Protected by AuthGuard (via layout)
 */
export default function AccountWorkspaceRoute() {
  return <AccountWorkspacePage />;
}