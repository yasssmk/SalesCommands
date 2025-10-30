// frontend/src/components/csv/CSVDataPreview.jsx

/**
 * CSV Data Preview Component
 * 
 * Displays a table preview of parsed CSV data with validation status
 * Shows valid rows (green) and invalid rows (red)
 * Reusable across all entities (Users, Accounts, Contacts, etc.)
 */

import PropTypes from 'prop-types';

// material-ui
import { useTheme } from '@mui/material/styles';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import ScrollX from 'components/ScrollX';

// ==============================|| CSV DATA PREVIEW ||============================== //

/**
 * Display CSV data preview table
 * 
 * @param {Object} parsedData - Parsed CSV data
 * @param {Array<string>} parsedData.headers - Column headers
 * @param {Array<Object>} parsedData.data - Row data
 * @param {Object} validationResult - Validation results
 * @param {Array<Object>} validationResult.validRows - Valid rows
 * @param {Array<Object>} validationResult.invalidRows - Invalid rows
 * @param {Object} validationResult.stats - Statistics
 * @param {number} maxRows - Maximum rows to display (default: 10)
 * @param {string} title - Table title
 */
export default function CSVDataPreview({
  parsedData,
  validationResult,
  maxRows = 10,
  title
}) {
  const theme = useTheme();

  if (!parsedData || !validationResult) return null;

  const { headers } = parsedData;
  const { validRows, invalidRows, stats } = validationResult;

  // Calculate how many of each type to show
  const validToShow = Math.min(validRows.length, Math.floor(maxRows / 2));
  const invalidToShow = Math.min(invalidRows.length, maxRows - validToShow);
  const totalShown = validToShow + invalidToShow;

  const displayTitle = title || `Data Preview (showing first ${totalShown} rows)`;

  return (
    <MainCard title={displayTitle} sx={{ bgcolor: 'transparent' }}>
      <ScrollX>
        <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ minWidth: 50 }}>#</TableCell>
                <TableCell sx={{ minWidth: 80 }}>Status</TableCell>
                {headers.map((header) => (
                  <TableCell key={header} sx={{ minWidth: 120 }}>
                    {header}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {/* Valid rows (green background) */}
              {validRows.slice(0, validToShow).map((row) => (
                <TableRow key={`valid-${row._rowIndex}`} hover>
                  <TableCell>{row._rowIndex}</TableCell>
                  <TableCell>
                    <Chip 
                      label="Valid" 
                      size="small" 
                      color="success" 
                    />
                  </TableCell>
                  {headers.map((header) => {
                    // Convention: si _original{Header} existe, l'afficher (ex: _originalRole)
                    const originalKey = `_original${header.charAt(0).toUpperCase() + header.slice(1)}`;
                    const displayValue = row[originalKey] || row[header];
                    
                    return (
                      <TableCell key={header}>
                        {displayValue?.toString() || '-'}
                      </TableCell>
                    );
                  })}
                  </TableRow>   
                ))} 
              
              {/* Invalid rows (red background) */}
              {invalidRows.slice(0, invalidToShow).map((row) => (
                <TableRow 
                  key={`invalid-${row._rowIndex}`} 
                  hover
                  sx={{ bgcolor: theme.palette.error.lighter }}
                >
                  <TableCell>{row._rowIndex}</TableCell>
                  <TableCell>
                    <Chip 
                      label="Invalid" 
                      size="small" 
                      color="error" 
                    />
                  </TableCell>
                  {headers.map((header) => {
                    // Convention: si _original{Header} existe, l'afficher (ex: _originalRole)
                    const originalKey = `_original${header.charAt(0).toUpperCase() + header.slice(1)}`;
                    const displayValue = row[originalKey] || row[header];
                    
                    return (
                      <TableCell key={header}>
                        {displayValue?.toString() || '-'}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}

              {/* Show more rows indicator */}
              {stats.total > totalShown && (
                <TableRow>
                  <TableCell colSpan={headers.length + 2} align="center">
                    <Typography variant="body2" color="textSecondary">
                      ... and {stats.total - totalShown} more rows
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </ScrollX>
    </MainCard>
  );
}

CSVDataPreview.propTypes = {
  parsedData: PropTypes.shape({
    headers: PropTypes.arrayOf(PropTypes.string).isRequired,
    data: PropTypes.arrayOf(PropTypes.object).isRequired
  }),
  validationResult: PropTypes.shape({
    validRows: PropTypes.arrayOf(PropTypes.object).isRequired,
    invalidRows: PropTypes.arrayOf(PropTypes.object).isRequired,
    stats: PropTypes.shape({
      total: PropTypes.number.isRequired,
      valid: PropTypes.number.isRequired,
      invalid: PropTypes.number.isRequired
    }).isRequired
  }),
  maxRows: PropTypes.number,
  title: PropTypes.string
};