import { useState, useCallback, useEffect} from 'react';
import PropTypes from 'prop-types';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Chip from '@mui/material/Chip';

// project imports
import MainCard from 'components/MainCard';
import UploadCSV from 'components/third-party/dropzone/UploadCSV';
import ScrollX from 'components/ScrollX';
import BulkProgressBar from 'components/third-party/dropzone/BulkProgressBar';
import BulkImportReport from 'components/third-party/dropzone/BulkImportReport';

//api
import { createBulkUsers } from 'api/admin/users';
import { handleApiError } from 'utils/errorHandler'; 

// utils
import { parseCSVFile } from 'utils/csvParser';
import { validateUserCSVData, prepareUserDataForAPI, getUserCSVColumns, getUserCSVGuidelines, generateSampleCSV } from './userCSVValidation';
import { buildLookups, getAvailableValues } from './resolvers';
import { isValidUUID } from 'utils/validators';

// assets
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import DownloadOutlined from '@ant-design/icons/DownloadOutlined';
import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';

// ==============================|| USER CSV IMPORT MODAL ||============================== //

export default function UserCSVImportModal({ open, onClose, onImport }) {
  const theme = useTheme();
  
  // States
  const [file, setFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [parseError, setParseError] = useState(null);
  const [parsedData, setParsedData] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [importResponse, setImportResponse] = useState(null);
  
  // New state for lookups
  const [lookups, setLookups] = useState(null);
  const [lookupsLoading, setLookupsLoading] = useState(false);
  const [lookupsError, setLookupsError] = useState(null);
  
  // Import progress state
  const [importProgress, setImportProgress] = useState({
    total: 0,
    processed: 0,
    success: 0,
    failed: 0,
    skipped: 0
  });

  // 🔧 Helper: reset complet de l'état du modal
  const resetState = useCallback(() => {
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
    setLookupsError(null);
  }, []);

  // ♻️ Reset auto à l'ouverture du modal + préfetch lookups
  useEffect(() => {
    if (open) {
      resetState();
      // Préfetch lookups
      loadLookups();
      console.debug('[UserCSVImportModal] open=true → reset state + fetch lookups');
    } else {
      console.debug('[UserCSVImportModal] open=false');
    }
  }, [open, resetState]);

  // Load lookups for name resolution
  const loadLookups = async () => {
    setLookupsLoading(true);
    setLookupsError(null);
    
    try {
      const lookupsData = await buildLookups();
      setLookups(lookupsData);
      console.debug('[UserCSVImportModal] Lookups loaded successfully');
    } catch (error) {
      console.error('[UserCSVImportModal] Failed to load lookups:', error);
      setLookupsError(error.message || 'Failed to load reference data');
    } finally {
      setLookupsLoading(false);
    }
  };

  // Get column definitions
  const expectedColumns = getUserCSVColumns();
  const csvGuidelines = getUserCSVGuidelines();

  // Handle file selection
  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    // Reset states when new file is selected
    if (!selectedFile) {
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
    }
  };

  // Process CSV file
  const handleProcessCSV = async (csvFile) => {
    setProcessing(true);
    setParseError(null);
    
    try {
      // Parse CSV
      const parseResult = await parseCSVFile(csvFile);
      
      if (!parseResult.success) {
        setParseError(parseResult.error);
        return;
      }

      setParsedData(parseResult);

      // Validate data with lookups for name resolution
      const validation = validateUserCSVData(parseResult.data, lookups);
      setValidationResult(validation);

    } catch (error) {
      setParseError(error.message || 'Failed to process CSV file');
    } finally {
      setProcessing(false);
    }
  };

  // Download sample CSV
  const handleDownloadSample = () => {
    const csvContent = generateSampleCSV(lookups);
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'users_import_sample.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  // Handle import
  const handleImport = async () => {
    if (!validationResult || validationResult.validRows.length === 0) {
      console.warn('[UserCSVImportModal] handleImport → no validRows, abort');
      return;
    }

    console.log('[UserCSVImportModal] handleImport start');

    setImporting(true);
    setImportResponse(null);
    setParseError(null);

    const totalToImport = validationResult.validRows.length;
    const BATCH_SIZE = 50;

    // Progress init
    setImportProgress({
      total: totalToImport,
      processed: 0,
      success: 0,
      failed: 0,
      skipped: 0
    });

    const apiData = prepareUserDataForAPI(validationResult.validRows);

    const cumulativeResults = {
      success: [],
      failed: [],
      skipped: []
    };

    let topLevelHttpStatus = 0;
    let topLevelErrorMessage = '';

    try {
      for (let i = 0; i < apiData.length; i += BATCH_SIZE) {
        const batch = apiData.slice(i, Math.min(i + BATCH_SIZE, apiData.length));
        const batchIndex = i / BATCH_SIZE + 1;

        console.log(`[UserCSVImportModal] Batch ${batchIndex} (${i + 1} → ${i + batch.length})`);

        try {
          const batchResponse = await createBulkUsers(batch, 'partial');
          console.debug('[UserCSVImportModal] [BatchResponse]', batchResponse);

          // === Erreurs “transport/permission” → aucune results ===
          if (!batchResponse || (!batchResponse.results && batchResponse.success !== true)) {
            // essaye d’extraire un message propre (DRF 403, etc.)
            const msg = batchResponse?.error
              ? handleApiError(batchResponse.error)
              : 'Bulk import request failed (no results)';

            // status si dispo
            const st = batchResponse?.error?.response?.status || batchResponse?.httpStatus || 0;
            if (st) topLevelHttpStatus = st;
            if (msg) topLevelErrorMessage = msg;

            console.warn('[UserCSVImportModal] Batch error (no results), mark each line as failed:', { status: st, msg });

            const failedBatch = batch.map((user, idx) => ({
              row: i + idx + 1,
              email: user?.email || '(unknown)',
              errors: [msg || 'Request failed']
            }));

            cumulativeResults.failed.push(...failedBatch);
          }
          // === Backend renvoie des résultats détaillés
          else if (batchResponse?.results) {
            cumulativeResults.success.push(...(batchResponse.results.success || []));
            cumulativeResults.failed.push(...(batchResponse.results.failed || []));
            cumulativeResults.skipped.push(...(batchResponse.results.skipped || []));
          }
          // === Success sans details (très rare) → marquer skipped
          else if (batchResponse?.success === true) {
            console.warn('[UserCSVImportModal] Success but no results array → mark as skipped for traceability');
            const skippedBatch = batch.map((user, idx) => ({
              row: i + idx + 1,
              email: user?.email || '(unknown)',
              reason: 'No detailed results returned by server'
            }));
            cumulativeResults.skipped.push(...skippedBatch);
          }

          // Progress
          const processed = Math.min(i + BATCH_SIZE, apiData.length);
          setImportProgress(prev => ({
            ...prev,
            processed,
            success: cumulativeResults.success.length,
            failed: cumulativeResults.failed.length,
            skipped: cumulativeResults.skipped.length
          }));

          if (processed < apiData.length) {
            await new Promise(r => setTimeout(r, 50));
          }
        } catch (batchErr) {
          const msg = handleApiError(batchErr);
          const st = batchErr?.response?.status || 0;
          if (st) topLevelHttpStatus = st;
          if (msg) topLevelErrorMessage = msg;

          console.error(`[UserCSVImportModal] Batch ${batchIndex} exception`, { status: st, msg, err: batchErr });

          const failedBatch = batch.map((user, idx) => ({
            row: i + idx + 1,
            email: user?.email || '(unknown)',
            errors: [msg || 'Batch import failed']
          }));
          cumulativeResults.failed.push(...failedBatch);

          const processed = Math.min(i + BATCH_SIZE, apiData.length);
          setImportProgress(prev => ({
            ...prev,
            processed,
            failed: cumulativeResults.failed.length
          }));
        }
      }

      const finalResponse = {
        success: cumulativeResults.failed.length === 0 && cumulativeResults.skipped.length === 0,
        message: `Import completed: ${cumulativeResults.success.length} created, ${cumulativeResults.failed.length} failed, ${cumulativeResults.skipped.length} skipped`,
        summary: {
          total: totalToImport,
          success: cumulativeResults.success.length,
          failed: cumulativeResults.failed.length,
          skipped: cumulativeResults.skipped.length
        },
        results: cumulativeResults,
        httpStatus: topLevelHttpStatus || undefined,
        errorMessage: topLevelErrorMessage || undefined
      };

      console.debug('[UserCSVImportModal] FinalResponse', finalResponse);

      setImportResponse(finalResponse);

      if (onImport) {
        try {
          console.debug('[UserCSVImportModal] onImport call');
          onImport(finalResponse);
        } catch (cbErr) {
          console.warn('[UserCSVImportModal] onImport threw:', cbErr);
        }
      }
    } catch (err) {
      const msg = handleApiError(err);
      const st = err?.response?.status || 0;

      console.error('[UserCSVImportModal] handleImport global exception', { status: st, msg, err });

      const errorResponse = {
        success: false,
        message: msg || 'Import failed',
        summary: {
          total: totalToImport,
          success: 0,
          failed: totalToImport,
          skipped: 0
        },
        results: {
          success: [],
          failed: apiData.map((u, idx) => ({
            row: idx + 1,
            email: u?.email || '(unknown)',
            errors: [msg || 'Import failed']
          })),
          skipped: []
        },
        httpStatus: st || undefined,
        errorMessage: msg || undefined
      };

      setImportResponse(errorResponse);

      if (onImport) {
        try {
          onImport(errorResponse);
        } catch (cbErr) {
          console.warn('[UserCSVImportModal] onImport threw after error:', cbErr);
        }
      }
    } finally {
      setImportProgress(prev => ({ ...prev, processed: totalToImport }));
      setImporting(false);
    }
  };


  const handleRetryFailed = async () => {
    // Pré-conditions
    if (!importResponse || !importResponse.results || !validationResult) return;

    const prevSuccess = importResponse.results.success || [];
    const prevFailed = importResponse.results.failed || [];
    const prevSkipped = importResponse.results.skipped || [];

    if (prevFailed.length === 0) return; // rien à rejouer

    // 1) Construire la payload de retry à partir des lignes échouées
    //    → On mappe par numéro de ligne (_rowIndex) prioritairement, sinon par email
    const failedRowsSet = new Set(
      prevFailed
        .map((it) => (typeof it.row === 'number' ? it.row : parseInt(it.row, 10)))
        .filter((n) => !Number.isNaN(n))
    );

    // Sous-ensemble des validRows initiaux correspondant aux lignes échouées
    const rowsToRetry = validationResult.validRows.filter((row) => {
      if (failedRowsSet.has(row._rowIndex)) return true;
      // fallback par email si besoin (duplication possible mais cas rare, MVP ok)
      const email = (row.email || '').toLowerCase().trim();
      return prevFailed.some(
        (f) => (f.email || '').toLowerCase().trim() === email
      );
    });

    if (rowsToRetry.length === 0) {
      // Rien à rejouer (ex. si les données ont été modifiées côté CSV)
      return;
    }

    // 2) Préparer les données pour l'API (retire les champs internes _rowIndex/_errors/_isValid)
    const retryApiData = prepareUserDataForAPI(rowsToRetry);

    // 3) Initialiser une progression locale pour le retry
    const RETRY_BATCH_SIZE = 50;
    setImporting(true);
    setImportProgress({
      total: rowsToRetry.length,
      processed: 0,
      success: 0,
      failed: 0,
      skipped: 0
    });

    // 4) Lancer l'import par batch (mode partial)
    const newRetrySuccess = [];
    const newRetryFailed = [];

    try {
      for (let i = 0; i < retryApiData.length; i += RETRY_BATCH_SIZE) {
        const batch = retryApiData.slice(i, Math.min(i + RETRY_BATCH_SIZE, retryApiData.length));

        try {
          const batchResponse = await createBulkUsers(batch, 'partial');

          // Cumuler les résultats du batch de retry
          if (batchResponse?.results) {
            // Success du batch (pas de row dans la réponse backend → on tente de re-dériver le row depuis rowsToRetry)
            const batchSuccess = (batchResponse.results.success || []).map((s, idx) => {
              // retrouver le row d'origine si possible (par email)
              const match = rowsToRetry.find(r => (r.email || '').toLowerCase().trim() === (s.email || '').toLowerCase().trim());
              return {
                ...s,
                row: match?._rowIndex ?? s.row // garde row si backend l'a déjà fourni
              };
            });
            newRetrySuccess.push(...batchSuccess);

            // Failed du batch → messages déjà structurés
            const batchFailed = (batchResponse.results.failed || []).map((f) => {
              // s'assurer qu'on a bien le numéro de ligne si possible
              if (typeof f.row !== 'number') {
                const match = rowsToRetry.find(r => (r.email || '').toLowerCase().trim() === (f.email || '').toLowerCase().trim());
                return { ...f, row: match?._rowIndex ?? f.row };
              }
              return f;
            });
            newRetryFailed.push(...batchFailed);
          }

          // Progression
          const processed = Math.min(i + RETRY_BATCH_SIZE, retryApiData.length);
          setImportProgress((prev) => ({
            ...prev,
            processed,
            success: newRetrySuccess.length,
            failed: newRetryFailed.length
          }));

          if (processed < retryApiData.length) {
            await new Promise((resolve) => setTimeout(resolve, 100));
          }
        } catch (batchError) {
          // Batch complet en échec → marquer toutes les lignes du batch comme failed
          batch.forEach((user, idx) => {
            const match = rowsToRetry[i + idx];
            newRetryFailed.push({
              row: match?._rowIndex ?? i + idx + 1,
              email: user.email,
              errors: ['Batch import failed: ' + (batchError.message || 'Unknown error')]
            });
          });

          // Mettre à jour la progression malgré tout
          const processed = Math.min(i + RETRY_BATCH_SIZE, retryApiData.length);
          setImportProgress((prev) => ({
            ...prev,
            processed,
            failed: newRetryFailed.length
          }));
        }
      }

      // 5) Construire la nouvelle réponse consolidée :
      //    - success = anciens succès + nouveaux succès
      //    - failed  = seulement les échecs restants après retry
      //    - skipped = inchangé (doublons en requête initiale, etc.)
      const mergedSuccess = [...prevSuccess, ...newRetrySuccess];

      // On conserve uniquement les échecs “restants”.
      // Critère : ligne (row) ou email persiste dans newRetryFailed.
      const remainingFailed = newRetryFailed.length > 0
        ? newRetryFailed
        : []; // Si tout a réussi au retry, plus de failed.

      // Summary global : basé sur le total initial
      const totalInitial = importResponse.summary?.total || (prevSuccess.length + prevFailed.length + prevSkipped.length);
      const updatedSummary = {
        total: totalInitial,
        success: mergedSuccess.length,
        failed: remainingFailed.length,
        skipped: prevSkipped.length
      };

      const updatedResponse = {
        success: remainingFailed.length === 0 && prevSkipped.length === 0,
        message: `Import completed: ${updatedSummary.success} imported, ${updatedSummary.failed} failed${updatedSummary.skipped ? `, ${updatedSummary.skipped} skipped` : ''}`,
        summary: updatedSummary,
        results: {
          success: mergedSuccess,
          failed: remainingFailed,
          skipped: prevSkipped
        }
      };

      setImportResponse(updatedResponse);

      // Mettre à jour la progression finale du retry (affiche la perf du retry uniquement)
      setImportProgress((prev) => ({
        ...prev,
        processed: prev.total
      }));
    } catch (err) {
      // Erreur globale de retry → ne pas écraser l'ancien importResponse, juste signaler en progression
      console.error('Retry error:', err);
    } finally {
      setImporting(false);
    }
  };

  // Handle close
  const handleClose = () => {
    if (!processing && !importing) {
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
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      aria-labelledby="user-csv-import-dialog"
    >
      <DialogTitle>
        {importResponse ? 'Import Results' : 'Import Users from CSV'}
      </DialogTitle>
      <Divider />

      {importResponse && importResponse.success === false && (
        <Box sx={{ mt: 2 }}>
          <Alert severity="error">
            <AlertTitle>
              {importResponse.httpStatus ? `Error ${importResponse.httpStatus}` : 'Import Error'}
            </AlertTitle>
            {importResponse.errorMessage }
          </Alert>
        </Box>
      )}
      <DialogContent sx={{ p: 2.5 }}>
        <Grid container spacing={3}>
          {/* Upload Section - Masqué après import*/}
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

          {/* Expected Format - Masqué après import*/}
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
              <Button
                  size="small"
                  startIcon={<DownloadOutlined />}
                  onClick={handleDownloadSample}  // ✅ Utilise la fonction ici
                  disabled={lookupsLoading}
                >
                  Download Sample CSV
                </Button>
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
          {validationResult && !importResponse &&  (
            <Grid item xs={12}>
              <Stack direction="row" spacing={2}>
                <Chip 
                  label={`Total: ${validationResult.stats.total}`} 
                  color="default" 
                />
                <Chip 
                  icon={<CheckCircleOutlined />}
                  label={`Valid: ${validationResult.stats.valid}`} 
                  color="success" 
                />
                {validationResult.stats.invalid > 0 && (
                  <Chip 
                    icon={<CloseCircleOutlined />}
                    label={`Invalid: ${validationResult.stats.invalid}`} 
                    color="error" 
                  />
                )}
                {validationResult.stats.duplicates > 0 && (
                  <Chip 
                    label={`Duplicates: ${validationResult.stats.duplicates}`} 
                    color="warning" 
                  />
                )}
              </Stack>
            </Grid>
          )}

          {/* Validation Errors */}
          {validationResult && validationResult.allErrors.length > 0 && !importResponse &&  (
            <Grid item xs={12}>
              <Alert severity="warning">
                <AlertTitle>Validation Issues</AlertTitle>
                <Box sx={{ maxHeight: 150, overflow: 'auto' }}>
                  {validationResult.allErrors.slice(0, 10).map((error, index) => (
                    <Typography key={index} variant="body2" sx={{ mb: 0.5 }}>
                      • {error}
                    </Typography>
                  ))}
                  {validationResult.allErrors.length > 10 && (
                    <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                      ... and {validationResult.allErrors.length - 10} more errors
                    </Typography>
                  )}
                </Box>
              </Alert>
            </Grid>
          )}

          {/* Import Progress */}
          {importProgress.total > 0 && (
            <Grid item xs={12}>
              <BulkProgressBar
                operation="Importing Users"
                total={importProgress.total}
                processed={importProgress.processed}
                success={importProgress.success}
                failed={importProgress.failed}
                skipped={importProgress.skipped}
                variant={importing ? 'default' : 'inline'}
              />
            </Grid>
          )}

          {importResponse && importResponse.results && (
            <Grid item xs={12}>
              <BulkImportReport
                results={importResponse.results}
                entityName="users"
                showSuccessDetails={true}
                onRetry={handleRetryFailed}
                sx={{ mt: 1 }}
              />
            </Grid>
          )}


          {/* Data Preview */}
          {parsedData && validationResult && !importResponse && (
            <Grid item xs={12}>
              <MainCard 
                title={`Data Preview (showing first 10 rows)`}
                sx={{ bgcolor: 'transparent' }}
              >
                <ScrollX>
                  <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
                    <Table stickyHeader size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ minWidth: 50 }}>#</TableCell>
                          <TableCell sx={{ minWidth: 80 }}>Status</TableCell>
                          {parsedData.headers.map((header) => (
                            <TableCell key={header} sx={{ minWidth: 120 }}>
                              {header}
                            </TableCell>
                          ))}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {/* Show valid rows first */}
                        {validationResult.validRows.slice(0, 5).map((row) => (
                          <TableRow key={`valid-${row._rowIndex}`} hover>
                            <TableCell>{row._rowIndex}</TableCell>
                            <TableCell>
                              <Chip 
                                label="Valid" 
                                size="small" 
                                color="success" 
                              />
                            </TableCell>
                            {parsedData.headers.map((header) => (
                              <TableCell key={header}>
                                {row[header]?.toString() || '-'}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}
                        
                        {/* Show invalid rows */}
                        {validationResult.invalidRows.slice(0, 5).map((row) => (
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
                            {parsedData.headers.map((header) => (
                              <TableCell key={header}>
                                {row[header]?.toString() || '-'}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}

                        {/* Show more rows indicator */}
                        {validationResult.stats.total > 10 && (
                          <TableRow>
                            <TableCell colSpan={parsedData.headers.length + 2} align="center">
                              <Typography variant="body2" color="textSecondary">
                                ... and {validationResult.stats.total - 10} more rows
                              </Typography>
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </ScrollX>
              </MainCard>
            </Grid>
          )}
        </Grid>
      </DialogContent>
      
      <Divider />    
      
      <DialogActions sx={{ p: 2.5 }}>
        <Grid container justifyContent="space-between" alignItems="center">
          <Grid item />
          <Grid item>
            {/* AJOUT: Bouton New Import après succès */}
            {importResponse && importProgress.success > 0 && (
              <Button
                variant="outlined"
                onClick={() => {
                  // Reset tout pour un nouvel import
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
                }}
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
              
              {/* MODIFIÉ: Import button masqué après import */}
              {!importResponse && (
                <Button
                  variant="contained"
                  onClick={handleImport}
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
                    `Import ${validationResult?.stats.valid || 0} Valid Users`
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

UserCSVImportModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onImport: PropTypes.func.isRequired
};