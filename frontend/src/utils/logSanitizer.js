// frontend/src/utils/logSanitizer.js

/**
 * Log Sanitizer - PII Redaction Utility
 * 
 * Protects sensitive information in logs by masking:
 * - Email addresses
 * - JWT tokens and API keys
 * - Sensitive HTTP headers (Authorization, Cookie, etc.)
 * - UUIDs in specific contexts
 * 
 * @module utils/logSanitizer
 */

// ==============================|| PATTERNS ||============================== //

const PATTERNS = {
  // Email pattern: user@example.com → u***@example.com
  EMAIL: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
  
  // JWT pattern: eyJ... → eyJ***
  JWT: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g,
  
  // Bearer token pattern: Bearer eyJ... → Bearer ***
  BEARER: /Bearer\s+[A-Za-z0-9._-]+/gi,
  
  // API key pattern (common formats)
  API_KEY: /[A-Za-z0-9]{32,}/g,
};

// Sensitive header names to redact
const SENSITIVE_HEADERS = [
  'authorization',
  'cookie',
  'set-cookie',
  'x-api-key',
  'x-auth-token',
  'x-csrf-token',
  'x-xsrf-token',
];

// ==============================|| REDACTION FUNCTIONS ||============================== //

/**
 * Mask email addresses in text
 * user@example.com → u***@example.com
 * 
 * @param {string} text - Text potentially containing emails
 * @returns {string} Text with masked emails
 */
export const sanitizeEmail = (text) => {
  if (typeof text !== 'string') return text;
  
  return text.replace(PATTERNS.EMAIL, (email) => {
    const [localPart, domain] = email.split('@');
    const maskedLocal = localPart.length > 1 
      ? `${localPart[0]}***` 
      : '***';
    return `${maskedLocal}@${domain}`;
  });
};

/**
 * Mask JWT tokens and Bearer tokens
 * eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... → eyJ***
 * Bearer eyJ... → Bearer ***
 * 
 * @param {string} text - Text potentially containing tokens
 * @returns {string} Text with masked tokens
 */
export const sanitizeToken = (text) => {
  if (typeof text !== 'string') return text;
  
  // Mask JWT tokens
  let sanitized = text.replace(PATTERNS.JWT, 'eyJ***[REDACTED]');
  
  // Mask Bearer tokens
  sanitized = sanitized.replace(PATTERNS.BEARER, 'Bearer ***[REDACTED]');
  
  return sanitized;
};

/**
 * Mask API keys and long alphanumeric strings
 * 
 * @param {string} text - Text potentially containing API keys
 * @returns {string} Text with masked keys
 */
export const sanitizeApiKey = (text) => {
  if (typeof text !== 'string') return text;
  
  return text.replace(PATTERNS.API_KEY, (match) => {
    // Only mask if it looks like a key (32+ chars, no spaces)
    if (match.length >= 32 && !/\s/.test(match)) {
      return `${match.substring(0, 8)}***[REDACTED]`;
    }
    return match;
  });
};

/**
 * Sanitize HTTP headers object
 * Redacts sensitive headers like Authorization, Cookie, etc.
 * 
 * @param {Object} headers - Headers object
 * @returns {Object} Sanitized headers
 */
export const sanitizeHeaders = (headers) => {
  if (!headers || typeof headers !== 'object') return headers;
  
  const sanitized = {};
  
  for (const [key, value] of Object.entries(headers)) {
    const lowerKey = key.toLowerCase();
    
    if (SENSITIVE_HEADERS.includes(lowerKey)) {
      sanitized[key] = '***[REDACTED]';
    } else if (typeof value === 'string') {
      // Still sanitize tokens in non-sensitive headers
      sanitized[key] = sanitizeToken(value);
    } else {
      sanitized[key] = value;
    }
  }
  
  return sanitized;
};

/**
 * Deep sanitization of objects and arrays
 * Recursively sanitizes all string values
 * 
 * @param {any} obj - Object/array/primitive to sanitize
 * @param {number} depth - Current recursion depth (prevents infinite loops)
 * @returns {any} Sanitized version
 */
export const sanitizeObject = (obj, depth = 0) => {
  // Prevent infinite recursion
  if (depth > 10) return '[MAX_DEPTH]';
  
  // Handle null/undefined
  if (obj === null || obj === undefined) return obj;
  
  // Handle primitives
  if (typeof obj !== 'object') {
    if (typeof obj === 'string') {
      let sanitized = sanitizeEmail(obj);
      sanitized = sanitizeToken(sanitized);
      return sanitized;
    }
    return obj;
  }
  
  // Handle Arrays
  if (Array.isArray(obj)) {
    return obj.map(item => sanitizeObject(item, depth + 1));
  }
  
  // Handle special case: headers object
  if (obj.headers && typeof obj.headers === 'object') {
    return {
      ...obj,
      headers: sanitizeHeaders(obj.headers),
    };
  }
  
  // Handle Objects
  const sanitized = {};
  
  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.toLowerCase();
    
    // Redact specific sensitive keys
    if (
      lowerKey.includes('password') ||
      lowerKey.includes('secret') ||
      lowerKey.includes('token') ||
      lowerKey === 'authorization' ||
      lowerKey === 'cookie'
    ) {
      sanitized[key] = '***[REDACTED]';
    } else {
      sanitized[key] = sanitizeObject(value, depth + 1);
    }
  }
  
  return sanitized;
};

/**
 * Main sanitization function for console logs
 * Can be used as drop-in replacement for console.log/warn/error
 * 
 * @param {...any} args - Arguments to sanitize
 * @returns {Array} Sanitized arguments array
 * 
 * @example
 * const sanitized = sanitizeLog("User: user@test.com", { token: "eyJ..." });
 * console.log(...sanitized);
 */
export const sanitizeLog = (...args) => {
  try {
    return args.map(arg => {
      // Handle strings
      if (typeof arg === 'string') {
        let sanitized = sanitizeEmail(arg);
        sanitized = sanitizeToken(sanitized);
        return sanitized;
      }
      
      // Handle objects
      if (typeof arg === 'object') {
        return sanitizeObject(arg);
      }
      
      // Handle other primitives
      return arg;
    });
  } catch (error) {
    // Fallback: if sanitization fails, return original
    // Better to log unsanitized than to lose the log entirely
    console.error('[SANITIZER ERROR]', error);
    return args;
  }
};

// ==============================|| SAFE CONSOLE WRAPPERS ||============================== //

/**
 * Safe console methods with automatic sanitization
 * Use these instead of direct console.log/warn/error
 */
export const safeConsole = {
  log: (...args) => {
    console.log(...sanitizeLog(...args));
  },
  
  warn: (...args) => {
    console.warn(...sanitizeLog(...args));
  },
  
  error: (...args) => {
    console.error(...sanitizeLog(...args));
  },
  
  info: (...args) => {
    console.info(...sanitizeLog(...args));
  },
  
  debug: (...args) => {
    if (process.env.NODE_ENV === 'development') {
      console.debug(...sanitizeLog(...args));
    }
  },
};

// ==============================|| EXPORTS ||============================== //

export default {
  sanitizeEmail,
  sanitizeToken,
  sanitizeApiKey,
  sanitizeHeaders,
  sanitizeObject,
  sanitizeLog,
  safeConsole,
};