// frontend/src/app/(protected)/businessData/contacts/page.jsx

import ContactsListPage from 'views/businessData/contacts/list';

// ==============================|| CONTACTS PAGE ||============================== //

/**
 * Next.js App Router page component for Contact Management
 * 
 * Protected by AuthGuard (via layout)
 * Imports the actual component from views/businessData/contacts/list.jsx
 */
export default function ContactsPage() {
  return <ContactsListPage />;
}

// ==============================|| METADATA ||============================== //

/**
 * Page metadata for SEO and security
 */
export const metadata = {
  title: 'Contact Management',
  description: 'Manage contacts',
  robots: 'noindex, nofollow' // Admin pages should not be indexed
};