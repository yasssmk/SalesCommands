import PropTypes from 'prop-types';

// PROJECT IMPORTS  
import DashboardLayout from 'layout/DashboardLayout';
import AuthGuard from 'utils/route-guard/AuthGuard';

// Vue temporaire vide
function DashboardHome() {
  return (
    <div>
      <h1>Dashboard Home - En construction</h1>
      <p>Cette page utilisera DashboardLayout</p>
    </div>
  );
}

// ==============================|| DASHBOARD LAYOUT ||============================== //

export default function DashboardLayoutWrapper({ children }) {
  return (
    <AuthGuard>
      {/* <DashboardLayout> */}
        {children}
      {/* </DashboardLayout> */}
    </AuthGuard>
  );
}

DashboardLayoutWrapper.propTypes = { 
  children: PropTypes.node.isRequired 
};