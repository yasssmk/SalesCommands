// frontend/src/app/(protected)/territories/[id]/page.jsx

import TerritoryWorkspacePage from 'views/territories/workspace';

// ==============================|| TERRITORY WORKSPACE PAGE ||============================== //

/**
 * Next.js App Router page component for Territory Workspace
 * 
 * Dynamic route that displays territory details with tabs:
 * - Summary
 * - List (accounts)
 * - Activities
 * 
 * Protected by AuthGuard (via layout)
 */
export default function TerritoryWorkspaceRoute() {
  return <TerritoryWorkspacePage />;
}

// ==============================|| METADATA ||============================== //

export const metadata = {
  title: 'Territory Workspace',
  description: 'View territory details and accounts',
  robots: 'noindex, nofollow'
};