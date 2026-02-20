// frontend/src/app/(protected)/campaigns/page.jsx

import CampaignsListPage from 'views/campaigns/list';

// ==============================|| CAMPAIGNS PAGE ||============================== //

/**
 * Next.js App Router page component for Campaigns
 *
 * Located in Go-To-Market section
 * Protected by AuthGuard (via layout)
 */
export default function CampaignsPage() {
  return <CampaignsListPage />;
}

// ==============================|| METADATA ||============================== //

export const metadata = {
  title: 'Campaigns',
  description: 'Manage sales campaigns and sequences',
  robots: 'noindex, nofollow'
};