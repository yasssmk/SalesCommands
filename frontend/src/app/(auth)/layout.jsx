import PropTypes from 'prop-types';
// PROJECT IMPORTS
import PublicGuard from 'utils/route-guard/PublicGuard';

// ==============================|| DASHBOARD LAYOUT ||============================== //

export default function AuthLayout({ children }) {
  return (
    <PublicGuard >
      {children}
    </PublicGuard>
  );
}

AuthLayout.propTypes = { 
  children: PropTypes.node.isRequired 
};
