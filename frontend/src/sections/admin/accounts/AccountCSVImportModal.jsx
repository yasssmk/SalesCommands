// frontend/src/sections/admin/accounts/AccountCSVImportModal.jsx

/**
 * Account CSV Import Modal - Simple Wrapper
 * 
 * Lightweight wrapper around the generic CSVImportModal
 * Provides account-specific configuration via accountCSVConfig
 */

import PropTypes from 'prop-types';

// Generic CSV Import Modal
import CSVImportModal from 'components/csv/CSVImportModal';

// Account-specific configuration
import { accountCSVConfig } from './accountCSVConfig';

// ==============================|| ACCOUNT CSV IMPORT MODAL ||============================== //

/**
 * CSV Import Modal for Accounts
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close handler
 * @param {Function} onImport - Success callback (receives import response)
 */
export default function AccountCSVImportModal({ open, onClose, onImport }) {
  return (
    <CSVImportModal
      config={accountCSVConfig}
      open={open}
      onClose={onClose}
      onImport={onImport}
    />
  );
}

AccountCSVImportModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onImport: PropTypes.func.isRequired
};