// frontend/src/sections/admin/users/UserCSVImportModal.jsx

/**
 * User CSV Import Modal - Simple Wrapper
 * 
 * Lightweight wrapper around the generic CSVImportModal
 * Provides user-specific configuration via userCSVConfig
 * 
 * Reduced from 870 lines to 20 lines through refactoring
 */

import PropTypes from 'prop-types';

// Generic CSV Import Modal
import CSVImportModal from 'components/csv/CSVImportModal';

// User-specific configuration
import { userCSVConfig } from './userCSVConfig';

// ==============================|| USER CSV IMPORT MODAL ||============================== //

/**
 * CSV Import Modal for Users
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close handler
 * @param {Function} onImport - Success callback (receives import response)
 */
export default function UserCSVImportModal({ open, onClose, onImport }) {
  return (
    <CSVImportModal
      config={userCSVConfig}
      open={open}
      onClose={onClose}
      onImport={onImport}
    />
  );
}

UserCSVImportModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onImport: PropTypes.func.isRequired
};