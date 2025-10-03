import PropTypes from 'prop-types';

// material-ui
import { alpha, styled } from '@mui/material/styles';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';

// third-party
import { useDropzone } from 'react-dropzone';

// project imports
import RejectionFiles from './RejectionFiles';

// assets
import CloudUploadOutlined from '@ant-design/icons/CloudUploadOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';

const DropzoneWrapper = styled('div')(({ theme }) => ({
  outline: 'none',
  padding: theme.spacing(5, 1),
  borderRadius: theme.shape.borderRadius,
  backgroundColor: theme.palette.background.paper,
  border: `1px dashed ${theme.palette.secondary.main}`,
  '&:hover': { opacity: 0.72, cursor: 'pointer' }
}));

// ==============================|| UPLOAD - CSV ||============================== //

export default function UploadCSV({ 
  file, 
  onFileSelect, 
  onProcess,
  processing = false,
  error,
  sx,
  showPreview = true 
}) {
  const {
    getRootProps,
    getInputProps,
    isDragActive,
    isDragReject,
    fileRejections
  } = useDropzone({
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.csv']
    },
    multiple: false,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        onFileSelect(acceptedFiles[0]);
      }
    }
  });

  const handleRemove = () => {
    onFileSelect(null);
  };

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <Box sx={sx}>
          <DropzoneWrapper
            {...getRootProps()}
            sx={{
              ...(isDragActive && { opacity: 0.72 }),
              ...((isDragReject || error) && {
                color: 'error.main',
                borderColor: 'error.light',
                bgcolor: 'error.lighter'
              }),
              ...(file && {
                padding: '12px 0'
              })
            }}
          >
            <input {...getInputProps()} />
            
            <Stack
              spacing={2}
              alignItems="center"
              justifyContent="center"
              direction={{ xs: 'column', md: 'row' }}
              sx={{ width: 1, textAlign: { xs: 'center', md: 'left' } }}
            >
              {!file ? (
                <>
                  <CloudUploadOutlined style={{ fontSize: '32px' }} />
                  <Stack sx={{ p: 3 }} spacing={1}>
                    <Typography variant="h5">Drag & Drop or Select CSV file</Typography>
                    <Typography color="secondary">
                      Drop files here or click&nbsp;
                      <Typography component="span" color="primary" sx={{ textDecoration: 'underline' }}>
                        browse
                      </Typography>
                      &nbsp;through your machine
                    </Typography>
                  </Stack>
                </>
              ) : (
                <>
                  <FileTextOutlined style={{ fontSize: '32px', color: '#00c853' }} />
                  <Stack spacing={0.5} sx={{ p: 3 }}>
                    <Typography variant="h6">{file.name}</Typography>
                    <Typography variant="body2" color="secondary">
                      Size: {(file.size / 1024).toFixed(2)} KB
                    </Typography>
                  </Stack>
                </>
              )}
            </Stack>
          </DropzoneWrapper>

          {fileRejections.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="error">
                <AlertTitle>Invalid File Type</AlertTitle>
                <Typography variant="body2">
                  Please upload a CSV file (*.csv)
                </Typography>
              </Alert>
            </Box>
          )}
        </Box>
      </Grid>

      {file && (
        <Grid item xs={12}>
          <Stack direction="row" justifyContent="space-between" spacing={1.5}>
            <Button color="error" onClick={handleRemove} disabled={processing}>
              Remove
            </Button>
            {onProcess && (
              <Button 
                variant="contained" 
                onClick={() => onProcess(file)}
                disabled={processing}
                startIcon={processing ? <LinearProgress size={20} /> : null}
              >
                {processing ? 'Processing...' : 'Process CSV'}
              </Button>
            )}
          </Stack>
        </Grid>
      )}
    </Grid>
  );
}

UploadCSV.propTypes = {
  file: PropTypes.object,
  onFileSelect: PropTypes.func.isRequired,
  onProcess: PropTypes.func,
  processing: PropTypes.bool,
  error: PropTypes.bool,
  sx: PropTypes.object,
  showPreview: PropTypes.bool
};