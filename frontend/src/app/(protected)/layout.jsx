'use client';
import PropTypes from 'prop-types';

// project imports
import DashboardLayout from 'layout/DashboardLayout';
import AuthGuard from 'utils/route-guard/AuthGuard';
import ErrorBoundary from 'components/ErrorBoundary';

// ==============================|| PROTECTED LAYOUT WITH ERROR BOUNDARY ||============================== //

export default function Layout({ children }) {
  return (
    <AuthGuard>
      <ErrorBoundary name="ProtectedLayout">
        <DashboardLayout>
          <ErrorBoundary name="PageContent">
            {children}
          </ErrorBoundary>
        </DashboardLayout>
      </ErrorBoundary>
    </AuthGuard>
  );
}

Layout.propTypes = {
  children: PropTypes.node
};