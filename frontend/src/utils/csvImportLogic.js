// frontend/src/utils/csvImportLogic.js

/**
 * Generic CSV Import Logic - Reusable Hooks
 * 
 * Provides all the business logic for CSV import operations:
 * - State management
 * - File processing & validation
 * - Bulk import with batching
 * - Retry logic for failed imports
 * 
 * Usage:
 * const csvImport = useCSVImport(userCSVConfig);
 * 
 * This hook is entity-agnostic and works for Users, Accounts, Contacts, etc.
 */

import { useState, useCallback, useEffect } from 'react';
import { parseCSVFile } from './csvParser';
import { handleApiError } from './errorHandler';
import { handleBulkError } from './bulkErrorHandler';

// ==============================|| MAIN HOOK ||============================== //

/**
 * Complete CSV Import Hook
 * Manages the entire CSV import lifecycle
 * 
 * @param {Object} config - Entity-specific configuration (from userCSVConfig.js)
 * @param {boolean} open - Modal open state (triggers reset)
 * @returns {Object} All states and handlers needed for CSV import
 */
export function useCSVImport(config, open = false) {
  // States
  const [file, setFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [parseError, setParseError] = useState(null);
  const [parsedData, setParsedData] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [importResponse, setImportResponse] = useState(null);
  const [lookups, setLookups] = useState(null);
  const [lookupsLoading, setLookupsLoading] = useState(false);
  const [lookupsError, setLookupsError] = useState(null);
  const [importProgress, setImportProgress] = useState({
    total: 0,
    processed: 0,
    success: 0,
    failed: 0,
    skipped: 0
  });

  // Reset state
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

  // Auto-reset when modal opens
  useEffect(() => {
    if (open) {
      resetState();
      if (config.buildLookups) {
        loadLookups();
      }
      console.debug(`[useCSVImport] open=true → reset state + fetch lookups for ${config.entity}`);
    }
  }, [open, resetState, config.entity, config.buildLookups]);

  // Load lookups
  const loadLookups = async () => {
    if (!config.buildLookups) {
      console.debug('[useCSVImport] No buildLookups function provided');
      return;
    }

    setLookupsLoading(true);
    setLookupsError(null);
    
    try {
      const lookupsData = await config.buildLookups();
      setLookups(lookupsData);
      console.debug('[useCSVImport] Lookups loaded successfully');
    } catch (error) {
      console.error('[useCSVImport] Failed to load lookups:', error);
      setLookupsError(error.message || 'Failed to load reference data');
    } finally {
      setLookupsLoading(false);
    }
  };

  // Handle file selection
  const handleFileSelect = useCallback((selectedFile) => {
    setFile(selectedFile);
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
  }, []);

  // Process CSV file
  const handleProcessCSV = useCallback(async (csvFile) => {
    setProcessing(true);
    setParseError(null);
    
    try {
      const parseResult = await parseCSVFile(csvFile);
      
      if (!parseResult.success) {
        setParseError(parseResult.error);
        return;
      }

      setParsedData(parseResult);

      // Validate with config validator
      const validation = config.validateData(parseResult.data, lookups);
      setValidationResult(validation);

    } catch (error) {
      setParseError(error.message || 'Failed to process CSV file');
    } finally {
      setProcessing(false);
    }
  }, [config, lookups]);

  // Handle import
  // Handle import
const handleImport = useCallback(async () => {
  if (!validationResult || validationResult.validRows.length === 0) {
    console.warn('[useCSVImport] handleImport → no validRows, abort');
    return;
  }

  console.log(`[useCSVImport] Starting import for ${config.entity}`);

  setImporting(true);
  setImportResponse(null);
  setParseError(null);

  const totalToImport = validationResult.validRows.length;
  const BATCH_SIZE = config.options?.batchSize || 50;
  const BATCH_DELAY = config.options?.batchDelay || 50;

  setImportProgress({
    total: totalToImport,
    processed: 0,
    success: 0,
    failed: 0,
    skipped: 0
  });

  const apiData = config.prepareForAPI(validationResult.validRows);

  const cumulativeResults = {
    success: [],
    failed: [],
    skipped: []
  };

  let pendingResponse = null;
  let topLevelHttpStatus = 0;
  let topLevelErrorMessage = '';

  try {
    for (let i = 0; i < apiData.length; i += BATCH_SIZE) {
      const batch = apiData.slice(i, Math.min(i + BATCH_SIZE, apiData.length));
      const batchIndex = i / BATCH_SIZE + 1;

      console.log(`[useCSVImport] Batch ${batchIndex} (${i + 1} → ${i + batch.length})`);

      try {
        const batchResponse = await config.bulkCreate(batch, 'partial');
        console.debug('[useCSVImport] [BatchResponse]', batchResponse);

        if (!pendingResponse && (batchResponse?.isPending || batchResponse?.status === 'pending')) {
          const pendingMessage = batchResponse?.message ||
            'Operation still in progress. It will complete in the background.';

          pendingResponse = {
            ...batchResponse,
            isPending: true,
            status: batchResponse?.status || 'pending',
            message: pendingMessage,
            results: batchResponse?.results || {
              success: [],
              failed: [],
              skipped: []
            },
            summary: batchResponse?.summary
          };

          const processed = Math.min(i + batch.length, apiData.length);
          setImportProgress(prev => ({
            ...prev,
            processed
          }));

          break;
        }


        // Check if this is an error response (success: false)
        if (batchResponse?.success === false) {
          console.debug('[useCSVImport] Error response path - batchResponse structure:', {
            success: batchResponse.success,
            hasError: !!batchResponse?.error,
            errorType: typeof batchResponse?.error,
            errorKeys: batchResponse?.error ? Object.keys(batchResponse.error) : [],
            batchResponseKeys: Object.keys(batchResponse)
          });

          // Extract error object
          const errorObj = batchResponse?.error;
          
          // Extract status (error object is plain { status, message, response })
          const st = errorObj?.status ||
                    errorObj?.response?.status ||
                    batchResponse?.httpStatus ||
                    batchResponse?.status ||
                    0;
          
          // Extract message
          const msg = errorObj?.message ||
                     batchResponse?.message ||
                     'Bulk import request failed';

          // Store for finalResponse
          if (st) topLevelHttpStatus = st;
          if (msg) topLevelErrorMessage = msg;

          console.warn('[useCSVImport] Batch error (success: false):', { status: st, msg, errorObj });

          // Mark entire batch as failed
          const failedBatch = batch.map((item, idx) => ({
            row: i + idx + 1,
            email: item?.email || '(unknown)',
            errors: [msg || 'Request failed']
          }));

          cumulativeResults.failed.push(...failedBatch);
        }
        // Results returned with data
        else if (batchResponse?.results) {
          cumulativeResults.success.push(...(batchResponse.results.success || []));
          cumulativeResults.failed.push(...(batchResponse.results.failed || []));
          cumulativeResults.skipped.push(...(batchResponse.results.skipped || []));
        }
        // Success without details
        else {
          console.warn('[useCSVImport] Unexpected response format:', batchResponse);
          const skippedBatch = batch.map((item, idx) => ({
            row: i + idx + 1,
            email: item?.email || '(unknown)',
            reason: 'No detailed results returned by server'
          }));
          cumulativeResults.skipped.push(...skippedBatch);
        }

        // Update progress
        const processed = Math.min(i + BATCH_SIZE, apiData.length);
        setImportProgress(prev => ({
          ...prev,
          processed,
          success: cumulativeResults.success.length,
          failed: cumulativeResults.failed.length,
          skipped: cumulativeResults.skipped.length
        }));

        if (processed < apiData.length) {
          await new Promise(r => setTimeout(r, BATCH_DELAY));
        }
      } catch (batchErr) {
        const msg = handleApiError(batchErr);
        const st = batchErr?.response?.status || 0;
        if (st) topLevelHttpStatus = st;
        if (msg) topLevelErrorMessage = msg;

        console.error(`[useCSVImport] Batch ${batchIndex} exception`, { status: st, msg });

        const failedBatch = batch.map((item, idx) => ({
          row: i + idx + 1,
          email: item?.email || '(unknown)',
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

    if (pendingResponse) {
      const normalizedResults = pendingResponse.results || {
        success: [...cumulativeResults.success],
        failed: [...cumulativeResults.failed],
        skipped: [...cumulativeResults.skipped]
      };

      const normalizedSummary = pendingResponse.summary && Object.keys(pendingResponse.summary).length > 0
        ? {
            total: pendingResponse.summary.total ?? pendingResponse.summary.requested ?? totalToImport,
            success: pendingResponse.summary.success ??
                     pendingResponse.summary.created ??
                     pendingResponse.summary.updated ??
                     pendingResponse.summary.deleted ??
                     pendingResponse.summary.archived ??
                     (normalizedResults.success?.length || 0),
            failed: pendingResponse.summary.failed ?? (normalizedResults.failed?.length || 0),
            skipped: pendingResponse.summary.skipped ?? (normalizedResults.skipped?.length || 0)
          }
        : {
            total: totalToImport,
            success: normalizedResults.success?.length || 0,
            failed: normalizedResults.failed?.length || 0,
            skipped: normalizedResults.skipped?.length || 0
          };

      const responseToReturn = {
        ...pendingResponse,
        results: normalizedResults,
        summary: normalizedSummary
      };

      setImportResponse(null);
      return responseToReturn;
    }

    // Debug log before building response
    console.debug('[useCSVImport] Before finalResponse:', { 
      topLevelHttpStatus, 
      topLevelErrorMessage,
      successCount: cumulativeResults.success.length,
      failedCount: cumulativeResults.failed.length
    });

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

    console.debug('[useCSVImport] FinalResponse', finalResponse);
    setImportResponse(finalResponse);

    // Display snackbar for 0% success (total failure)
    if (finalResponse.success === false && finalResponse.summary.success === 0) {
      console.log('[useCSVImport] 0% success detected → calling handleBulkError for snackbar');
      handleBulkError(finalResponse, null, {
        onComplete: null
      });
    }

    return finalResponse;

  } catch (err) {
    const msg = handleApiError(err);
    const st = err?.response?.status || 0;

    console.error('[useCSVImport] handleImport global exception', { status: st, msg });

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
        failed: apiData.map((item, idx) => ({
          row: idx + 1,
          email: item?.email || '(unknown)',
          errors: [msg || 'Import failed']
        })),
        skipped: []
      },
      httpStatus: st || undefined,
      errorMessage: msg || undefined
    };

    setImportResponse(errorResponse);

    // Display snackbar for 0% success in catch block
    console.log('[useCSVImport] Exception with 0% success → calling handleBulkError for snackbar');
    handleBulkError(errorResponse, null, {
      onComplete: null
    });

    return errorResponse;

  } finally {
    setImportProgress(prev => ({ ...prev, processed: totalToImport }));
    setImporting(false);
  }
}, [config, validationResult]);

  // Handle retry
  const handleRetry = useCallback(async () => {
    if (!importResponse || !importResponse.results || !validationResult) return;

    const prevSuccess = importResponse.results.success || [];
    const prevFailed = importResponse.results.failed || [];
    const prevSkipped = importResponse.results.skipped || [];

    if (prevFailed.length === 0) return;

    const failedRowsSet = new Set(
      prevFailed
        .map((it) => (typeof it.row === 'number' ? it.row : parseInt(it.row, 10)))
        .filter((n) => !Number.isNaN(n))
    );

    const rowsToRetry = validationResult.validRows.filter((row) => {
      if (failedRowsSet.has(row._rowIndex)) return true;
      const email = (row.email || '').toLowerCase().trim();
      return prevFailed.some(
        (f) => (f.email || '').toLowerCase().trim() === email
      );
    });

    if (rowsToRetry.length === 0) return;

    const retryApiData = config.prepareForAPI(rowsToRetry);
    const RETRY_BATCH_SIZE = config.options?.batchSize || 50;

    setImporting(true);
    setImportProgress({
      total: rowsToRetry.length,
      processed: 0,
      success: 0,
      failed: 0,
      skipped: 0
    });

    const newRetrySuccess = [];
    const newRetryFailed = [];

    try {
      for (let i = 0; i < retryApiData.length; i += RETRY_BATCH_SIZE) {
        const batch = retryApiData.slice(i, Math.min(i + RETRY_BATCH_SIZE, retryApiData.length));

        try {
          const batchResponse = await config.bulkCreate(batch, 'partial');

          if (batchResponse?.results) {
            const batchSuccess = (batchResponse.results.success || []).map((s) => {
              const match = rowsToRetry.find(r => (r.email || '').toLowerCase().trim() === (s.email || '').toLowerCase().trim());
              return {
                ...s,
                row: match?._rowIndex ?? s.row
              };
            });
            newRetrySuccess.push(...batchSuccess);

            const batchFailed = (batchResponse.results.failed || []).map((f) => {
              if (typeof f.row !== 'number') {
                const match = rowsToRetry.find(r => (r.email || '').toLowerCase().trim() === (f.email || '').toLowerCase().trim());
                return { ...f, row: match?._rowIndex ?? f.row };
              }
              return f;
            });
            newRetryFailed.push(...batchFailed);
          }

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
          batch.forEach((item, idx) => {
            const match = rowsToRetry[i + idx];
            newRetryFailed.push({
              row: match?._rowIndex ?? i + idx + 1,
              email: item.email,
              errors: ['Batch import failed: ' + (batchError.message || 'Unknown error')]
            });
          });

          const processed = Math.min(i + RETRY_BATCH_SIZE, retryApiData.length);
          setImportProgress((prev) => ({
            ...prev,
            processed,
            failed: newRetryFailed.length
          }));
        }
      }

      const mergedSuccess = [...prevSuccess, ...newRetrySuccess];
      const remainingFailed = newRetryFailed.length > 0 ? newRetryFailed : [];
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
      setImportProgress((prev) => ({ ...prev, processed: prev.total }));

      return updatedResponse;

    } catch (err) {
      console.error('[useCSVImport] Retry error:', err);
    } finally {
      setImporting(false);
    }
  }, [config, importResponse, validationResult]);

  // Download sample
  const handleDownloadSample = useCallback(() => {
    const csvContent = config.generateSample(lookups);
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = config.options?.sampleFilename || `${config.entity}_import_sample.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }, [config, lookups]);

  return {
    // States
    file,
    processing,
    importing,
    parseError,
    parsedData,
    validationResult,
    importResponse,
    lookups,
    lookupsLoading,
    lookupsError,
    importProgress,
    
    // Handlers
    handleFileSelect,
    handleProcessCSV,
    handleImport,
    handleRetry,
    handleDownloadSample,
    resetState,
    
    // Setters (for manual control if needed)
    setFile,
    setParseError,
    setImportResponse
  };
}

// ==============================|| DEFAULT EXPORT ||============================== //

export default useCSVImport;