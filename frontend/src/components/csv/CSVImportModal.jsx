// frontend/src/components/csv/CSVImportModal.jsx

/**
 * Generic CSV Import Modal
 * 
 * Reusable modal for CSV import operations across all entities
 * Configured via a config object (userCSVConfig, accountCSVConfig, etc.)
 * 
 * Usage:
 * <CSVImportModal
 *   config={userCSVConfig}
 *   open={open}
 *   onClose={onClose}
 *   onImport={onImport}
 * />
 */

import PropTypes from 'prop-types';

// material-ui
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import UploadCSV from 'components/third-party/dropzone/UploadCSV';
import BulkProgressBar from 'components/third-party/dropzone/BulkProgressBar';
import BulkImportReport from 'components/third-party/dropzone/BulkImportReport';
import CSVValidationSummary from './CSVValidationSummary';
import CSVDataPreview from './CSVDataPreview';

// utils
import useCSVImport from 'utils/csvImportLogic';
import { notifyCSVImportOutcome } from 'utils/csvImportNotifications';

// assets
import DownloadOutlined from '@ant-design/icons/DownloadOutlined';

// ==============================|| GENERIC CSV IMPORT MODAL ||============================== //

/**
 * Generic CSV Import Modal Component
 * 
 * @param {Object} config - Entity-specific configuration (from userCSVConfig, etc.)
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close handler
 * @param {Function} onImport - Import success callback (receives import response)
 */
export default function CSVImportModal({ config, open, onClose, onImport }) {
  // Use generic CSV import hook with config
  const {
    file,
    processing,
    importing,
    parseError,
    parsedData,
    validationResult,
    importResponse,
    lookupsLoading,
    importProgress,
    handleFileSelect,
    handleProcessCSV,
    handleImport,
    handleRetry,
    handleDownloadSample,
    setFile,
    setParsedData,
    setValidationResult,
    setParseError,
    setImportProgress,
    setImportResponse
  } = useCSVImport(config, open);

  // Get configuration data
  const expectedColumns = config.getColumns();
  const csvGuidelines = config.getGuidelines();
  const entityDisplay = config.entityDisplay || 'Item';
  const entityDisplayPlural = config.entityDisplayPlural || 'Items';
  const enableRetry = config.options?.enableRetry ?? true;
  const showSuccessDetails = config.options?.showSuccessDetails ?? true;
  const maxErrorsDisplay = config.options?.maxErrorsDisplay ?? 10;
  const previewMaxRows = config.options?.previewMaxRows ?? 10;

  // Handle import with callback
  const handleImportWithCallback = async () => {
    const result = await handleImport();
    
    if (result) {
    // notifications centralisées (pas de 0% ici, déjà géré par handleBulkError dans le hook)
    notifyCSVImportOutcome(result, {
      entityLabel: (config.entityDisplayPlural || config.entityPlural || 'items').toLowerCase()
    });

    if (onImport) {
      try {
        await onImport(result);
      } catch (err) {
        console.warn('[CSVImportModal] onImport callback error:', err);
      }
    }
  }
};

  // Handle retry with callback
  const handleRetryWithCallback = async () => {
    const result = await handleRetry();
    
    if (result) {
    // notifications centralisées pour le retry
    notifyCSVImportOutcome(result, {
      entityLabel: (config.entityDisplayPlural || config.entityPlural || 'items').toLowerCase()
    });

    if (onImport) {
      try {
        await onImport(result);
      } catch (err) {
        console.warn('[CSVImportModal] onImport callback error after retry:', err);
      }
    }
  }
};

  // Handle close
  const handleClose = () => {
    if (!processing && !importing) {
      onClose();
    }
  };

  // Handle new import
  const handleNewImport = () => {
    setFile(null);
    setParsedData(null);
    setValidationResult(null);
    setParseError(null);
    setImportProgress({
      total: 0,
      processed: 0,
      success: 0,
      failed: 0,
      skipped: 0
    });
    setImportResponse(null);
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      aria-labelledby="csv-import-dialog"
    >
      <DialogTitle>
        {importResponse ? 'Import Results' : `Import ${entityDisplayPlural} from CSV`}
      </DialogTitle>
      <Divider />

      {/* Top-level error (HTTP errors, permissions, etc.) */}
      {importResponse && importResponse.success === false && importResponse.errorMessage && (
        <Box sx={{ p: 2.5, pb: 0 }}>
          <Alert severity="error">
            <AlertTitle>
              {importResponse.httpStatus ? `Error ${importResponse.httpStatus}` : 'Import Error'}
            </AlertTitle>
            {importResponse.errorMessage}
          </Alert>
        </Box>
      )}

      <DialogContent sx={{ p: 2.5 }}>
        <Grid container spacing={3}>
          {/* Upload Section - Hidden after import */}
          {!importResponse && (
            <Grid item xs={12}>
              <MainCard title="Select CSV File" sx={{ bgcolor: 'transparent' }}>
                <UploadCSV
                  file={file}
                  onFileSelect={handleFileSelect}
                  onProcess={handleProcessCSV}
                  processing={processing}
                  error={!!parseError}
                  showPreview={true}
                />
              </MainCard>
            </Grid>
          )}

          {/* Expected Format & Guidelines - Hidden after import */}
          {!importResponse && (
            <Grid item xs={12}>
              <Alert severity="info">
                <AlertTitle>Expected CSV Format</AlertTitle>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  The CSV file should contain the following columns:
                </Typography>
                <Box sx={{ mt: 1 }}>
                  {expectedColumns.map((col) => (
                    <Chip
                      key={col.key}
                      label={`${col.label}${col.required ? ' *' : ''}`}
                      size="small"
                      color={col.required ? 'primary' : 'default'}
                      sx={{ mr: 1, mb: 1 }}
                    />
                  ))}
                </Box>

                {/* Import Guidelines */}
                {csvGuidelines && csvGuidelines.length > 0 && (
                  <>
                    <Divider sx={{ my: 1.5 }} />
                    <Typography 
                      variant="caption" 
                      color="text.secondary" 
                      sx={{ fontWeight: 600, display: 'block', mb: 1 }}
                    >
                      Import Guidelines:
                    </Typography>
                    <Box component="ul" sx={{ pl: 3, m: 0 }}>
                      {csvGuidelines.map((rule, idx) => (
                        <Typography
                          key={idx}
                          component="li"
                          variant="caption"
                          color="text.secondary"
                          sx={{ mb: 0.5 }}
                        >
                          {rule}
                        </Typography>
                      ))}
                    </Box>
                  </>
                )}

                {/* Download Sample Button */}
                <Box sx={{ mt: 2 }}>
                  <Button
                    size="small"
                    startIcon={<DownloadOutlined />}
                    onClick={handleDownloadSample}
                    disabled={lookupsLoading}
                  >
                    Download Sample CSV
                  </Button>
                </Box>
              </Alert>
            </Grid>
          )}

          {/* Parse Error */}
          {parseError && (
            <Grid item xs={12}>
              <Alert severity="error" onClose={() => setParseError(null)}>
                <AlertTitle>Error</AlertTitle>
                {parseError}
              </Alert>
            </Grid>
          )}

          {/* Validation Summary */}
          {validationResult && !importResponse && (
            <Grid item xs={12}>
              <CSVValidationSummary
                stats={validationResult.stats}
                errors={validationResult.allErrors}
                maxErrorsDisplay={maxErrorsDisplay}
              />
            </Grid>
          )}

          {/* Import Progress */}
          {importProgress.total > 0 && (
            <Grid item xs={12}>
              <BulkProgressBar
                operation={`Importing ${entityDisplayPlural}`}
                total={importProgress.total}
                processed={importProgress.processed}
                success={importProgress.success}
                failed={importProgress.failed}
                skipped={importProgress.skipped}
                variant={importing ? 'default' : 'inline'}
              />
            </Grid>
          )}

          {/* Import Report */}
          {importResponse && importResponse.results && (
            <Grid item xs={12}>
              <BulkImportReport
                results={importResponse.results}
                entityName={config.entityPlural}
                showSuccessDetails={showSuccessDetails}
                onRetry={enableRetry ? handleRetryWithCallback : undefined}
                sx={{ mt: 1 }}
              />
            </Grid>
          )}

          {/* Data Preview */}
          {parsedData && validationResult && !importResponse && (
            <Grid item xs={12}>
              <CSVDataPreview
                parsedData={parsedData}
                validationResult={validationResult}
                maxRows={previewMaxRows}
              />
            </Grid>
          )}
        </Grid>
      </DialogContent>
      
      <Divider />    
      
      <DialogActions sx={{ p: 2.5 }}>
        <Grid container justifyContent="space-between" alignItems="center">
          <Grid item />
          <Grid item>
            {/* New Import button after success */}
            {importResponse && importProgress.success > 0 && (
              <Button
                variant="outlined"
                onClick={handleNewImport}
              >
                New Import
              </Button>
            )}
          </Grid>
          <Grid item>
            <Stack direction="row" spacing={2} alignItems="center">
              <Button 
                onClick={handleClose} 
                color={importResponse ? "primary" : "error"}
                variant={importResponse ? "contained" : "text"}
                disabled={processing || importing}
              >
                {importResponse ? 'Done' : 'Cancel'}
              </Button>
              
              {/* Import button - hidden after import */}
              {!importResponse && (
                <Button
                  variant="contained"
                  onClick={handleImportWithCallback}
                  disabled={
                    !validationResult || 
                    validationResult.stats.valid === 0 || 
                    processing || 
                    importing ||
                    importProgress.processed > 0
                  }
                >
                  {importing ? (
                    'Importing...'
                  ) : importProgress.processed > 0 ? (
                    importProgress.failed === 0 ? 'Import Complete' : 'Import Completed with Errors'
                  ) : (
                    `Import ${validationResult?.stats.valid || 0} Valid ${validationResult?.stats.valid === 1 ? entityDisplay : entityDisplayPlural}`
                  )}
                </Button>
              )}
            </Stack>
          </Grid>
        </Grid>
      </DialogActions>
    </Dialog>
  );
}

CSVImportModal.propTypes = {
  config: PropTypes.shape({
    entity: PropTypes.string.isRequired,
    entityPlural: PropTypes.string.isRequired,
    entityDisplay: PropTypes.string,
    entityDisplayPlural: PropTypes.string,
    getColumns: PropTypes.func.isRequired,
    getGuidelines: PropTypes.func.isRequired,
    validateData: PropTypes.func.isRequired,
    prepareForAPI: PropTypes.func.isRequired,
    generateSample: PropTypes.func.isRequired,
    buildLookups: PropTypes.func,
    bulkCreate: PropTypes.func.isRequired,
    options: PropTypes.shape({
      batchSize: PropTypes.number,
      batchDelay: PropTypes.number,
      sampleFilename: PropTypes.string,
      enableRetry: PropTypes.bool,
      showSuccessDetails: PropTypes.bool,
      maxErrorsDisplay: PropTypes.number,
      previewMaxRows: PropTypes.number
    })
  }).isRequired,
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onImport: PropTypes.func
};