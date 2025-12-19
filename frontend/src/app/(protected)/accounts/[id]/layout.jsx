// src/app/(protected)/accounts/[id]/layout.jsx

import PropTypes from 'prop-types';

// ==============================|| ACCOUNT WORKSPACE LAYOUT ||============================== //

/**
 * Layout for Account Workspace pages
 * 
 * This layout wraps the account detail/workspace pages.
 * Protected by AuthGuard via parent (protected) layout.
 * 
 * Note: ResourceGuardLayout not used here because workspace
 * has its own loading/error handling with useGetAccountWorkspace hook.
 */
export default function AccountWorkspaceLayout({ children }) {
  return children;
}

AccountWorkspaceLayout.propTypes = {
  children: PropTypes.node.isRequired
};

// ==============================|| METADATA ||============================== //

export const metadata = {
  title: 'Account Workspace',
  description: 'Account details and workspace',
  robots: 'noindex, nofollow'
};