// frontend/src/app/(protected)/page.jsx

import HomePage from 'views/home';

// ==============================|| HOME PAGE ||============================== //

/**
 * Next.js App Router landing page (route "/").
 * Role-aware Home, protected by AuthGuard (via the protected layout).
 */
export default function DashboardHome() {
  return <HomePage />;
}

// ==============================|| METADATA ||============================== //

export const metadata = {
  title: 'Home',
};
