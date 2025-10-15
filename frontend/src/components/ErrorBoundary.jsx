// frontend/src/components/ErrorBoundary.jsx
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

// ==============================|| ERROR BOUNDARY (IMPROVED) ||============================== //

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
      errorType: 'unknown'  // ✅ NEW: Classify error types
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  /**
   * ✅ NEW: Classify the error type for better user messaging
   */
  classifyError(error) {
    if (!error) return 'unknown';
    
    const errorStr = error.toString().toLowerCase();
    const stackStr = error.stack?.toLowerCase() || '';

    // Destructuring errors (the main issue we're fixing)
    if (
      errorStr.includes('cannot destructure') ||
      errorStr.includes('cannot read propert') ||
      errorStr.includes('undefined is not an object') ||
      errorStr.includes('null is not an object') ||
      stackStr.includes('destructur')
    ) {
      return 'destructuring';
    }

    // Network/API errors
    if (
      errorStr.includes('network') ||
      errorStr.includes('fetch') ||
      errorStr.includes('axios')
    ) {
      return 'network';
    }

    // Render errors
    if (
      errorStr.includes('rendering') ||
      errorStr.includes('hydration') ||
      stackStr.includes('react-dom')
    ) {
      return 'render';
    }

    return 'unknown';
  }

  componentDidCatch(error, errorInfo) {
    const errorType = this.classifyError(error);

    // ✅ Enhanced logging with classification
    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 ErrorBoundary [${this.props.name || 'Unknown'}] - Type: ${errorType}`);
      console.error('Error:', error);
      console.error('Stack:', errorInfo?.componentStack);
      console.groupEnd();
    }

    this.setState(prevState => ({
      error,
      errorInfo,
      errorType,
      errorCount: prevState.errorCount + 1
    }));
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorType: 'unknown'
    });
  };

  handleReload = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  /**
   * ✅ NEW: Get user-friendly message based on error type
   */
  getUserMessage(errorType) {
    switch (errorType) {
      case 'destructuring':
        return {
          title: 'Data Loading Error',
          message: 'There was an issue loading the data for this page. This has been logged and we\'ll fix it.',
          suggestion: 'Try refreshing the page or going back to the previous page.'
        };
      
      case 'network':
        return {
          title: 'Connection Error',
          message: 'Unable to connect to the server. Please check your internet connection.',
          suggestion: 'Make sure you\'re connected to the internet and try again.'
        };
      
      case 'render':
        return {
          title: 'Display Error',
          message: 'There was a problem displaying this content.',
          suggestion: 'Try refreshing the page. If the problem persists, clear your browser cache.'
        };
      
      default:
        return {
          title: 'Something went wrong',
          message: 'We encountered an unexpected error. The issue has been logged and we\'ll look into it.',
          suggestion: 'Try refreshing the page or going back to the previous page.'
        };
    }
  }

  render() {
    const { hasError, error, errorCount, errorType } = this.state;
    const { children, name, minimal } = this.props;

    if (!hasError) {
      return children;
    }

    const userMessage = this.getUserMessage(errorType);

    // Version minimale
    if (minimal) {
      return (
        <Card sx={{ p: 2, textAlign: 'center', bgcolor: 'error.lighter' }}>
          <Typography color="error" gutterBottom>
            {userMessage.title}
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
                {userMessage.title}
              </Typography>

              <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
                {userMessage.message}
              </Typography>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                {userMessage.suggestion}
              </Typography>

              {/* ✅ Development info with error type classification */}
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
                      {name && `[${name}] `}
                      Type: {errorType}
                      {'\n\n'}
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