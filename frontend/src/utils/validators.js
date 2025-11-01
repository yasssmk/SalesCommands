/**
 * Client-side validation & sanitization utilities
 * Phase 5.3 - Security & Robustness
 */

// ==============================|| UUID VALIDATION ||============================== //

/**
 * UUID v4 regex pattern
 * Format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
 */
const UUID_V4_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Validate if a value is a valid UUID v4.
 */
export function isValidUUID(value) {
  if (!value || typeof value !== 'string') return false;
  return UUID_V4_REGEX.test(value.trim());
}

/**
 * Validate multiple UUIDs at once.
 */
export function areValidUUIDs(values) {
  if (!Array.isArray(values)) return false;
  if (values.length === 0) return true;
  return values.every((v) => isValidUUID(v));
}

// ==============================|| STRING SANITIZATION ||============================== //

/**
 * Safely trim a value and return null when empty.
 */
export function trimString(value) {
  if (value === null || value === undefined) return null;
  const out = String(value).trim();
  return out.length > 0 ? out : null;
}

/**
 * Sanitize email address (trim + lowercase).
 */
export function sanitizeEmail(email) {
  const trimmed = trimString(email);
  if (!trimmed) return null;
  return trimmed.toLowerCase();
}

/**
 * Sanitize an object's string properties.
 * Recursively trims all string values in an object.
 * If `fields` est fourni, on ne nettoie que ces propriétés.
 */
export function sanitizeObject(obj, fields = null) {
  if (!obj || typeof obj !== 'object') return obj;

  const sanitized = { ...obj };
  const keysToSanitize = fields || Object.keys(sanitized);

  keysToSanitize.forEach((key) => {
    if (key in sanitized && typeof sanitized[key] === 'string') {
      const trimmed = trimString(sanitized[key]);
      sanitized[key] = trimmed === null ? '' : trimmed;
    }
  });

  return sanitized;
}

// ==============================|| ADDITIONAL STRING UTILITIES (CSV) ||============================== //

/**
 * Remove invisible/zero-width characters from string.
 */
export function stripInvisible(str) {
  if (!str || typeof str !== 'string') return str || '';

  const invisibleChars = [
    '\u200B', // ZWSP
    '\u200C', // ZWNJ
    '\u200D', // ZWJ
    '\uFEFF', // BOM
    '\u00AD', // Soft hyphen
    '\u2060', // Word joiner
    '\u180E', // Mongolian vowel separator
    '\u202A', // LRE
    '\u202B', // RLE
    '\u202C', // PDF
    '\u202D', // LRO
    '\u202E', // RLO
    '\u2061', // Function application
    '\u2062', // Invisible times
    '\u2063', // Invisible separator
    '\u2064'  // Invisible plus
  ];

  let cleaned = str;
  invisibleChars.forEach((c) => {
    cleaned = cleaned.split(c).join('');
  });
  return cleaned;
}

/**
 * Normalize a name field (first/last name).
 * - Remove invisibles
 * - Trim + collapse spaces
 * - Unicode NFKC
 */
export function normalizeName(name) {
  if (!name) return '';
  let s = String(name);
  s = stripInvisible(s);
  s = s.trim().replace(/\s+/g, ' ');
  if (s.normalize) s = s.normalize('NFKC');
  return s;
}

/**
 * Convert empty strings to null.
 */
export function toNullIfEmpty(value) {
  if (value === null || value === undefined) return null;
  const t = String(value).trim();
  return t.length > 0 ? t : null;
}

/**
 * Convert various boolean representations to boolean.
 * Supports: true/false, 1/0, yes/no, y/n, on/off (case-insensitive)
 */
export function toBooleanLoose(value) {
  if (typeof value === 'boolean') return value;
  if (value === null || value === undefined) return null;

  const v = String(value).toLowerCase().trim();
  const TRUE = ['true', '1', 'yes', 'y', 'on'];
  const FALSE = ['false', '0', 'no', 'n', 'off'];
  if (TRUE.includes(v)) return true;
  if (FALSE.includes(v)) return false;
  return null;
}

// ==============================|| EMAIL VALIDATION ||============================== //

/**
 * Simple email validation regex (non-RFC but sufficient).
 */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validate email format.
 */
export function isValidEmail(email) {
  if (!email || typeof email !== 'string') return false;
  return EMAIL_REGEX.test(email);
}

// ==============================|| CSV ROW SANITIZATION ||============================== //

// /**
//  * Sanitize a user row from CSV import (client-side).
//  * - Email required + format
//  * - Names normalized
//  * - Password optional (>=8 if provided)
//  * - Role/Organization/Team kept as trimmed strings (resolved later)
//  * - is_active accepts boolean-ish values
//  */
// export function sanitizeUserRow(rawRow) {
//   const issues = [];
//   const clean = {};

//   // Email (required)
//   if (rawRow.email) {
//     const email = sanitizeEmail(rawRow.email);
//     if (email && isValidEmail(email)) {
//       clean.email = email;
//     } else {
//       issues.push('Invalid email format');
//     }
//   } else {
//     issues.push('Email is required');
//   }

//   // Names (optional)
//   clean.first_name = normalizeName(rawRow.first_name);
//   clean.last_name = normalizeName(rawRow.last_name);

//   // Password (optional, >= 8)
//   if (rawRow.password) {
//     const pwd = trimString(rawRow.password);
//     if (pwd && pwd.length >= 8) {
//       clean.password = pwd;
//     } else {
//       issues.push('Password must be at least 8 characters');
//     }
//   }

//   // Role / Organization / Team (optional, resolved later)
//   if (rawRow.role) clean.role = trimString(rawRow.role);
//   if (rawRow.organization) clean.organization = trimString(rawRow.organization);
//   if (rawRow.team) clean.team = trimString(rawRow.team);

//   // Active status (optional)
//   if (
//     rawRow.active !== undefined &&
//     rawRow.active !== null &&
//     rawRow.active !== ''
//   ) {
//     const bool = toBooleanLoose(rawRow.active);
//     if (bool !== null) clean.active = bool;
//     else issues.push(`Invalid active status value: "${rawRow.active}"`);
//   }

//   return { clean, issues };
// }

// ==============================|| ID VALIDATION ||============================== //

/**
 * Validate if a value can be used as an ID (UUID or positive integer).
 */
export function isValidId(value) {
  if (value === null || value === undefined) return false;

  if (typeof value === 'string' && isValidUUID(value)) return true;

  if (typeof value === 'number' && Number.isInteger(value) && value > 0) {
    return true;
  }

  if (typeof value === 'string') {
    const n = Number(value);
    return !isNaN(n) && Number.isInteger(n) && n > 0;
    }
  return false;
}

// ==============================|| FORM VALIDATION HELPERS ||============================== //

/**
 * Validate form payload before API submission.
 * - Check required UUID fields
 * - Sanitize string fields
 */
export function validateFormPayload(payload, requiredUUIDs = []) {
  const errors = {};
  const sanitized = { ...payload };

  requiredUUIDs.forEach((field) => {
    const val = sanitized[field];
    if (!val) return; // nullable ok
    if (!isValidUUID(val)) errors[field] = `Invalid ${field} ID`;
  });

  Object.keys(sanitized).forEach((k) => {
    if (typeof sanitized[k] === 'string') {
      const t = trimString(sanitized[k]);
      sanitized[k] = t === null ? '' : t;
    }
  });

  return {
    valid: Object.keys(errors).length === 0,
    errors,
    sanitized
  };
}

/**
 * Format validation errors object to a sentence.
 */
export function formatValidationErrors(errors) {
  if (!errors || Object.keys(errors).length === 0) return '';
  return Object.values(errors).join('. ') + '.';
}

// ==============================|| DEFAULT BUNDLE EXPORT ||============================== //

export default {
  // UUID
  isValidUUID,
  areValidUUIDs,

  // Strings
  trimString,
  sanitizeEmail,
  sanitizeObject,
  stripInvisible,
  normalizeName,
  toNullIfEmpty,

  // Boolean
  toBooleanLoose,

  // Email
  isValidEmail,

  // ID
  isValidId,

  // Forms
  validateFormPayload,
  formatValidationErrors
};
