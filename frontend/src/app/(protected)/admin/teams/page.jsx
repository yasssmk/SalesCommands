// frontend/src/app/(protected)/admin/teams/page.jsx

import TeamsListPage from 'views/admin/teams/list';

/**
 * Next.js App Router page component for Teams
 * 
 * Protected by AuthGuard (via layout)
 */
export default function AdminTeamsPage() {
  return <TeamsListPage />;
}

/**
 * Page metadata
 */
export const metadata = {
  title: 'Teams',
  description: 'Manage teams and hierarchies',
  robots: 'noindex, nofollow'
};