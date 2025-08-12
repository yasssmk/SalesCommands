import PropTypes from 'prop-types';
import AuthGuard from 'utils/route-guard/AuthGuard';
import DashboardLayout from 'layout/DashboardLayout';

export default function ProtectedLayout({ children }) {
  return (
    <AuthGuard>
      <DashboardLayout>{children}</DashboardLayout>
    </AuthGuard>
  );
}
ProtectedLayout.propTypes = { children: PropTypes.node.isRequired };
