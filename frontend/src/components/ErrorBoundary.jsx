'use client';

import React, { Component } from 'react';
import PropTypes from 'prop-types';

// Material UI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import ReloadOutlined from '@ant-design/icons/ReloadOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';

// ==============================|| ERROR BOUNDARY ||============================== //

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log uniquement en console
    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 ErrorBoundary [${this.props.name || 'Unknown'}]`);
      console.error('Error:', error);
      console.error('Stack:', errorInfo?.componentStack);
      console.groupEnd();
    }

    this.setState(prevState => ({
      error,
      errorInfo,
      errorCount: prevState.errorCount + 1
    }));
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  handleReload = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  render() {
    const { hasError, error, errorCount } = this.state;
    const { children, name, minimal } = this.props;

    if (!hasError) {
      return children;
    }

    // Version minimale
    if (minimal) {
      return (
        <Card sx={{ p: 2, textAlign: 'center', bgcolor: 'error.lighter' }}>
          <Typography color="error" gutterBottom>
            Something went wrong
          </Typography>
          <Button 
            size="small" 
            onClick={this.handleReset}
            startIcon={<ReloadOutlined />}
          >
            Retry
          </Button>
        </Card>
      );
    }

    // Version complète
    return (
      <Container maxWidth="sm">
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '60vh',
            py: 4
          }}
        >
          <Card sx={{ width: '100%', textAlign: 'center' }}>
            <CardContent sx={{ p: 4 }}>
              <Box
                sx={{
                  display: 'inline-flex',
                  p: 2,
                  bgcolor: 'error.lighter',
                  borderRadius: '50%',
                  mb: 3
                }}
              >
                <WarningOutlined 
                  style={{ fontSize: 48, color: 'var(--mui-palette-error-main)' }} 
                />
              </Box>

              <Typography variant="h3" gutterBottom>
                Oops! Something went wrong
              </Typography>

              <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                We encountered an unexpected error. The issue has been logged and we'll look into it.
              </Typography>

              {process.env.NODE_ENV === 'development' && error && (
                <Card variant="outlined" sx={{ mb: 3, bgcolor: 'grey.50' }}>
                  <CardContent>
                    <Typography 
                      variant="caption" 
                      component="pre" 
                      sx={{ 
                        textAlign: 'left', 
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        fontSize: '0.75rem'
                      }}
                    >
                      {name && `[${name}]\n`}
                      {error.toString()}
                    </Typography>
                  </CardContent>
                </Card>
              )}

              <Stack direction="row" spacing={2} justifyContent="center">
                <Button 
                  variant="contained" 
                  onClick={this.handleReset}
                  startIcon={<ReloadOutlined />}
                >
                  Try Again
                </Button>
                <Button 
                  variant="outlined" 
                  onClick={this.handleReload}
                >
                  Reload Page
                </Button>
              </Stack>

              {process.env.NODE_ENV === 'development' && errorCount > 1 && (
                <Typography 
                  variant="caption" 
                  color="text.secondary" 
                  sx={{ mt: 2, display: 'block' }}
                >
                  Error occurred {errorCount} times
                </Typography>
              )}
            </CardContent>
          </Card>
        </Box>
      </Container>
    );
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired,
  name: PropTypes.string,
  minimal: PropTypes.bool
};

ErrorBoundary.defaultProps = {
  minimal: false
};

export default ErrorBoundary;