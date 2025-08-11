'use client';

// project import
import DashboardLayout from '../layout/DashboardLayout';
import AuthGuard from '../utils/route-guard/AuthGuard';

// Vue temporaire vide
function DashboardHome() {
  return (
    <div>
      <h1>Dashboard Home - En construction</h1>
      <p>Cette page utilisera DashboardLayout</p>
    </div>
  );
}

// ==============================|| PAGE RACINE ||============================== //

export default function HomePage() {
  return (
    <AuthGuard>
      {/* <DashboardLayout> */}
        <DashboardHome />
      {/* </DashboardLayout> */}
    </AuthGuard>
  );
}