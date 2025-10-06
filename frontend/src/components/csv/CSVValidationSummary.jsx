// frontend/src/components/csv/CSVValidationSummary.jsx

/**
 * CSV Validation Summary Component
 * 
 * Displays validation statistics and error messages for CSV imports
 * Reusable across all entities (Users, Accounts, Contacts, etc.)
 */

import PropTypes from 'prop-types';

// material-ui
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// assets
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';

// ==============================|| CSV VALIDATION SUMMARY ||============================== //

/**
 * Display validation statistics and errors
 * 
 * @param {Object} stats - Validation statistics
 * @param {number} stats.total - Total rows processed
 * @param {number} stats.valid - Valid rows count
 * @param {number} stats.invalid - Invalid rows count
 * @param {number} stats.duplicates - Duplicate rows count
 * @param {Array<string>} errors - Array of error messages
 * @param {number} maxErrorsDisplay - Maximum errors to show (default: 10)
 */
export default function CSVValidationSummary({ 
  stats, 
  errors = [], 
  maxErrorsDisplay = 10 
}) {
  if (!stats) return null;

  const hasErrors = errors.length > 0;
  const showMoreErrors = errors.length > maxErrorsDisplay;

  return (
    <>
      {/* Statistics Chips */}
      <Stack direction="row" spacing={2} sx={{ mb: hasErrors ? 2 : 0 }}>
        <Chip 
          label={`Total: ${stats.total}`} 
          color="default" 
        />
        <Chip 
          icon={<CheckCircleOutlined />}
          label={`Valid: ${stats.valid}`} 
          color="success" 
        />
        {stats.invalid > 0 && (
          <Chip 
            icon={<CloseCircleOutlined />}
            label={`Invalid: ${stats.invalid}`} 
            color="error" 
          />
        )}
        {stats.duplicates > 0 && (
          <Chip 
            label={`Duplicates: ${stats.duplicates}`} 
            color="warning" 
          />
        )}
      </Stack>

      {/* Error Messages */}
      {hasErrors && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          <AlertTitle>Validation Issues</AlertTitle>
          <Box sx={{ maxHeight: 150, overflow: 'auto' }}>
            {errors.slice(0, maxErrorsDisplay).map((error, index) => (
              <Typography key={index} variant="body2" sx={{ mb: 0.5 }}>
                • {error}
              </Typography>
            ))}
            {showMoreErrors && (
              <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                ... and {errors.length - maxErrorsDisplay} more errors
              </Typography>
            )}
          </Box>
        </Alert>
      )}
    </>
  );
}

CSVValidationSummary.propTypes = {
  stats: PropTypes.shape({
    total: PropTypes.number.isRequired,
    valid: PropTypes.number.isRequired,
    invalid: PropTypes.number.isRequired,
    duplicates: PropTypes.number
  }),
  errors: PropTypes.arrayOf(PropTypes.string),
  maxErrorsDisplay: PropTypes.number
};