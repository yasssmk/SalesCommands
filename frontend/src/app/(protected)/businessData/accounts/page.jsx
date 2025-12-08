// frontend/src/app/(protected)/admin/accounts/page.jsx

import AccountsListPage from 'views/businessData/accounts/list';

// ==============================|| ACCOUNTS PAGE ||============================== //

/**
 * Next.js App Router page component for Account Management
 * 
 * Protected by AuthGuard (via layout)
 * Imports the actual component from views/businessData/accounts/list.jsx
 */
export default function AdminAccountsPage() {
  return <AccountsListPage />;
}

// ==============================|| METADATA ||============================== //

/**
 * Page metadata for SEO and security
 */
export const metadata = {
  title: 'Account Management',
  description: 'Manage company accounts',
  robots: 'noindex, nofollow' // Admin pages should not be indexed
};