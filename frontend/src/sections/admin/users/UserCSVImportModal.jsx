import { useState } from 'react';
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
import IconButton from '@mui/material/IconButton';

// project imports
import { PopupTransition } from 'components/@extended/Transitions';
import MainCard from 'components/MainCard';
import UploadCSV from 'components/third-party/dropzone/UploadCSV';
import ScrollX from 'components/ScrollX';

// utils
import { parseCSVFile } from 'utils/csvParser';
import { validateUserCSVData, prepareUserDataForAPI, getUserCSVColumns } from './userCSVValidation';

// assets
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';

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

  // Get column definitions
  const expectedColumns = getUserCSVColumns();

  // Handle file selection
  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    // Reset states when new file is selected
    if (!selectedFile) {
      setParsedData(null);
      setValidationResult(null);
      setParseError(null);
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

      // Validate data
      const validation = validateUserCSVData(parseResult.data);
      setValidationResult(validation);

    } catch (error) {
      setParseError(error.message || 'Failed to process CSV file');
    } finally {
      setProcessing(false);
    }
  };

  // Handle import
  const handleImport = async () => {
    if (!validationResult || validationResult.validRows.length === 0) {
      return;
    }

    setImporting(true);
    try {
      const apiData = prepareUserDataForAPI(validationResult.validRows);
      await onImport(apiData);
      handleClose();
    } catch (error) {
      // Error handled by parent
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
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
    //   TransitionComponent={PopupTransition}
      maxWidth="lg"
      fullWidth
      aria-labelledby="user-csv-import-dialog"
    >
      {/* <DialogTitle id="user-csv-import-dialog">
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography >Import Users from CSV</Typography>
          <IconButton
            onClick={handleClose}
            color="secondary"
            disabled={processing || importing}
          >
            <CloseOutlined />
          </IconButton>
        </Stack>
      </DialogTitle> */}
      <DialogTitle>Import Users from CSV</DialogTitle>
      <Divider />

      <DialogContent sx={{ p: 2.5 }}>
        <Grid container spacing={3}>
          {/* Upload Section */}
          <Grid item xs={12}>
            <MainCard title="Select CSV File" sx={{ bgcolor: 'transparent' }}>
              <UploadCSV
                file={file}
                onFileSelect={handleFileSelect}
                onProcess={handleProcessCSV}
                processing={processing}
                error={!!parseError}
              />
            </MainCard>
          </Grid>

          {/* Expected Format */}
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
              <Typography variant="caption" color="textSecondary" sx={{ mt: 1, display: 'block' }}>
                * Required fields • Active Status values: true/false, 1/0, yes/no
              </Typography>
            </Alert>
          </Grid>

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
          {validationResult && (
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
          {validationResult && validationResult.allErrors.length > 0 && (
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

          {/* Data Preview */}
          {parsedData && validationResult && (
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
                <Stack direction="row" spacing={2} alignItems="center">
                    <Button 
                        onClick={handleClose} 
                        color="error"
                        disabled={processing || importing}
                        >
                        Cancel
                    </Button>
                    <Button
                        variant="contained"
                        onClick={handleImport}
                        disabled={
                            !validationResult || 
                            validationResult.stats.valid === 0 || 
                            processing || 
                            importing
                        }
                    >
                        {importing ? 'Importing...' : `Import ${validationResult?.stats.valid || 0} Valid Users`}
                    </Button>
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