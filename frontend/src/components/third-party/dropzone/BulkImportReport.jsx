import { useState, useRef, useMemo } from 'react';
import PropTypes from 'prop-types';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Collapse from '@mui/material/Collapse';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Chip from '@mui/material/Chip';

// third-party
import { CSVLink } from 'react-csv';

// assets
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import DownloadOutlined from '@ant-design/icons/DownloadOutlined';
import UpOutlined from '@ant-design/icons/UpOutlined';
import DownOutlined from '@ant-design/icons/DownOutlined';
import CopyOutlined from '@ant-design/icons/CopyOutlined';

// ==============================|| BULK IMPORT REPORT ||============================== //

function getTopErrors(failedItems, limit = 3) {
  const map = new Map();

  (failedItems || []).forEach((item) => {
    const messages = Array.isArray(item.errors)
      ? item.errors
      : (item.error ? [item.error] : []);

    messages.forEach((msg) => {
      const key = String(msg || '').trim();
      if (!key) return;

      const entry = map.get(key) || { count: 0, sampleRows: [] };
      entry.count += 1;
      if (entry.sampleRows.length < 3 && (item.row || item.row === 0)) {
        entry.sampleRows.push(item.row);
      }
      map.set(key, entry);
    });
  });

  return Array.from(map.entries())
    .map(([message, { count, sampleRows }]) => ({ message, count, sampleRows }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

export default function BulkImportReport({
  results,
  entityName = 'items',
  showSuccessDetails = false,
  onRetry,
  additionalColumns = [],
  sx = {}
}) {
  const theme = useTheme();
  const csvLinkRef = useRef(null);
  const [expandedSections, setExpandedSections] = useState({
    success: false,
    failed: true,
    skipped: true
  });

  // Extract results
  const successItems = results?.success || [];
  const failedItems = results?.failed || [];
  const skippedItems = results?.skipped || [];
  
  // Calculate totals
  const totalProcessed = successItems.length + failedItems.length + skippedItems.length;
  const hasErrors = failedItems.length > 0 || skippedItems.length > 0;
  const topErrors = useMemo(() => getTopErrors(failedItems, 3), [failedItems]);

  
  // Toggle section expansion
  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };
  
  // Prepare error data for CSV export
  const prepareErrorCSVData = () => {
    const csvData = [];
    
    // Add failed items
    failedItems.forEach(item => {
      csvData.push({
        status: 'Failed',
        row: item.row || '-',
        email: item.email || item.identifier || '-',
        errors: Array.isArray(item.errors) ? item.errors.join('; ') : item.error || '-',
        ...Object.fromEntries(additionalColumns.map(col => [col.key, item[col.key] || '-']))
      });
    });
    
    // Add skipped items
    skippedItems.forEach(item => {
      csvData.push({
        status: 'Skipped',
        row: item.row || '-',
        email: item.email || item.identifier || '-',
        errors: item.error || item.reason || '-',
        ...Object.fromEntries(additionalColumns.map(col => [col.key, item[col.key] || '-']))
      });
    });
    
    return csvData;
  };
  
  // CSV headers
  const errorCSVHeaders = [
    { label: 'Status', key: 'status' },
    { label: 'Row', key: 'row' },
    { label: 'Email/ID', key: 'email' },
    { label: 'Errors', key: 'errors' },
    ...additionalColumns.map(col => ({ label: col.label, key: col.key }))
  ];
  
  // Copy errors to clipboard
  const copyErrorsToClipboard = () => {
    const errorText = prepareErrorCSVData()
      .map(row => `Row ${row.row}: ${row.errors}`)
      .join('\n');
    
    navigator.clipboard.writeText(errorText);
    // TODO: Show snackbar notification
  };
  
  // Render section header
  const renderSectionHeader = (title, count, icon, color, section) => (
    <Stack
      direction="row"
      alignItems="center"
      justifyContent="space-between"
      sx={{
        p: 2,
        cursor: 'pointer',
        '&:hover': { bgcolor: 'action.hover' }
      }}
      onClick={() => toggleSection(section)}
    >
      <Stack direction="row" spacing={2} alignItems="center">
        {icon}
        <Typography variant="h5">{title}</Typography>
        <Chip
          label={count}
          size="small"
          color={color}
          variant="light"
        />
      </Stack>
      <IconButton size="small">
        {expandedSections[section] ? <UpOutlined /> : <DownOutlined />}
      </IconButton>
    </Stack>
  );
  
  // Render error list
  const renderErrorList = (items, type) => (
    <TableContainer sx={{ maxHeight: 400 }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>Row</TableCell>
            <TableCell>Email/ID</TableCell>
            <TableCell>Errors</TableCell>
            {additionalColumns.map(col => (
              <TableCell key={col.key}>{col.label}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item, index) => (
            <TableRow key={`${type}-${index}`} hover>
              <TableCell>{item.row || '-'}</TableCell>
              <TableCell>{item.email || item.identifier || '-'}</TableCell>
              <TableCell>
                {Array.isArray(item.errors) ? (
                  <Stack spacing={0.5}>
                    {item.errors.map((error, idx) => (
                      <Typography key={idx} variant="caption" color="error">
                        • {error}
                      </Typography>
                    ))}
                  </Stack>
                ) : (
                  <Typography variant="caption" color="error">
                    {item.error || item.reason || '-'}
                  </Typography>
                )}
              </TableCell>
              {additionalColumns.map(col => (
                <TableCell key={col.key}>
                  {item[col.key] || '-'}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  // Render success list (simplified)
  const renderSuccessList = () => (
    <TableContainer sx={{ maxHeight: 400 }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>Row</TableCell>
            <TableCell>Email/ID</TableCell>
            <TableCell>Name</TableCell>
            <TableCell>ID</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {successItems.map((item, index) => (
            <TableRow key={`success-${index}`} hover>
              <TableCell>{item.row || '-'}</TableCell>
              <TableCell>{item.email || item.identifier || '-'}</TableCell>
              <TableCell>{item.name || '-'}</TableCell>
              <TableCell>
                <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                  {item.id || '-'}
                </Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  if (totalProcessed === 0) {
    return (
      <Alert severity="info">
        <AlertTitle>No Results</AlertTitle>
        No {entityName} were processed.
      </Alert>
    );
  }

  return (
    <Stack spacing={2} sx={sx}>
      {/* Summary Alert */}
      <Alert
        severity={hasErrors ? 'warning' : 'success'}
        icon={hasErrors ? <WarningOutlined /> : <CheckCircleOutlined />}
      >
        <AlertTitle>
          Import {hasErrors ? 'Completed with Issues' : 'Successful'}
        </AlertTitle>
        <Typography variant="body2">
          {successItems.length} {entityName} imported successfully
          {failedItems.length > 0 && `, ${failedItems.length} failed`}
          {skippedItems.length > 0 && `, ${skippedItems.length} skipped`}
        </Typography>
      </Alert>

      {/* Action Buttons */}
      {hasErrors && (
        <Stack direction="row" spacing={2}>
          <Button
            variant="outlined"
            startIcon={<DownloadOutlined />}
            onClick={() => csvLinkRef.current?.link.click()}
            size="small"
          >
            Export Errors CSV
          </Button>
          <Button
            variant="outlined"
            startIcon={<CopyOutlined />}
            onClick={copyErrorsToClipboard}
            size="small"
          >
            Copy Errors
          </Button>
          {onRetry && (
            <Button
              variant="contained"
              onClick={onRetry}
              size="small"
            >
              Retry Failed Items
            </Button>
          )}
        </Stack>
      )}

      {/* Hidden CSV Download Link */}
      <CSVLink
        data={prepareErrorCSVData()}
        headers={errorCSVHeaders}
        filename={`import-errors-${new Date().toISOString().split('T')[0]}.csv`}
        ref={csvLinkRef}
        style={{ display: 'none' }}
      />

      {hasErrors && topErrors.length > 0 && (
        <Alert severity="warning">
          <AlertTitle>Top erreurs récurrentes</AlertTitle>
          <Stack spacing={0.75}>
            {topErrors.map((e, idx) => (
              <Typography key={idx} variant="body2">
                <strong>{e.count}×</strong> — {e.message}
                {e.sampleRows?.length > 0 && (
                  <> (ex. lignes {e.sampleRows.join(', ')})</>
                )}
              </Typography>
            ))}
          </Stack>
        </Alert>
      )}

      {/* Detailed Results */}
      <Stack spacing={2}>
        {/* Success Section */}
        {successItems.length > 0 && showSuccessDetails && (
          <Card>
            {renderSectionHeader(
              'Successfully Imported',
              successItems.length,
              <CheckCircleOutlined style={{ color: theme.palette.success.main, fontSize: 20 }} />,
              'success',
              'success'
            )}
            <Collapse in={expandedSections.success}>
              <Divider />
              <Box sx={{ p: 2 }}>
                {renderSuccessList()}
              </Box>
            </Collapse>
          </Card>
        )}

        {/* Failed Section */}
        {failedItems.length > 0 && (
          <Card>
            {renderSectionHeader(
              'Failed',
              failedItems.length,
              <CloseCircleOutlined style={{ color: theme.palette.error.main, fontSize: 20 }} />,
              'error',
              'failed'
            )}
            <Collapse in={expandedSections.failed}>
              <Divider />
              <Box sx={{ p: 2 }}>
                {renderErrorList(failedItems, 'failed')}
              </Box>
            </Collapse>
          </Card>
        )}

        {/* Skipped Section */}
        {skippedItems.length > 0 && (
          <Card>
            {renderSectionHeader(
              'Skipped',
              skippedItems.length,
              <WarningOutlined style={{ color: theme.palette.warning.main, fontSize: 20 }} />,
              'warning',
              'skipped'
            )}
            <Collapse in={expandedSections.skipped}>
              <Divider />
              <Box sx={{ p: 2 }}>
                {renderErrorList(skippedItems, 'skipped')}
              </Box>
            </Collapse>
          </Card>
        )}
      </Stack>
    </Stack>
  );
}

BulkImportReport.propTypes = {
  results: PropTypes.shape({
    success: PropTypes.array,
    failed: PropTypes.array,
    skipped: PropTypes.array
  }).isRequired,
  entityName: PropTypes.string,
  showSuccessDetails: PropTypes.bool,
  onRetry: PropTypes.func,
  additionalColumns: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired
  })),
  sx: PropTypes.object
};