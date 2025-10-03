/**
 * Generic CSV parser utility
 * Returns raw data without any validation
 */

// Supported delimiters to auto-detect
const DELIMITERS = [',', ';', '\t', '|'];

/**
 * Detect the most likely delimiter from a sample of text
 */
const detectDelimiter = (text) => {
  const sample = text.split('\n').slice(0, 5).join('\n');
  let maxCount = 0;
  let bestDelimiter = ',';

  DELIMITERS.forEach(delim => {
    const count = (sample.match(new RegExp(delim, 'g')) || []).length;
    if (count > maxCount) {
      maxCount = count;
      bestDelimiter = delim;
    }
  });

  return bestDelimiter;
};

/**
 * Parse a CSV line handling quoted values
 */
const parseCSVLine = (line, delimiter) => {
  const values = [];
  let current = '';
  let inQuotes = false;
  let i = 0;

  while (i < line.length) {
    const char = line[i];
    
    if (char === '"' || char === "'") {
      if (inQuotes && line[i + 1] === char) {
        // Escaped quote
        current += char;
        i += 2;
      } else {
        inQuotes = !inQuotes;
        i++;
      }
    } else if (char === delimiter && !inQuotes) {
      values.push(current.trim());
      current = '';
      i++;
    } else {
      current += char;
      i++;
    }
  }
  
  // Don't forget the last value
  values.push(current.trim());
  
  return values;
};

/**
 * Parse CSV file and return raw data
 * @param {File} file - CSV file to parse
 * @returns {Promise<{success: boolean, headers: Array, data: Array, delimiter: string, error?: string}>}
 */
export const parseCSVFile = async (file) => {
  try {
    // Validate file
    if (!file) {
      throw new Error('No file provided');
    }

    if (!file.name.endsWith('.csv') && file.type !== 'text/csv') {
      throw new Error('Please upload a CSV file');
    }

    // Read file
    const text = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsText(file);
    });

    if (!text || text.trim().length === 0) {
      throw new Error('File is empty');
    }

    // Detect delimiter
    const delimiter = detectDelimiter(text);

    // Split lines and remove empty ones
    const lines = text.trim().split(/\r?\n/).filter(line => line.trim());
    
    if (lines.length === 0) {
      throw new Error('No data found in file');
    }

    // Parse headers
    const headerValues = parseCSVLine(lines[0], delimiter);
    const headers = headerValues.map(h => 
      h.toLowerCase()
        .replace(/[^a-z0-9]/g, '_')
        .replace(/^_+|_+$/g, '')
        .replace(/_+/g, '_')
    );

    // Parse data rows
    const data = [];
    
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const values = parseCSVLine(line, delimiter);
      const rowData = {};
      
      // Map values to headers
      headers.forEach((header, index) => {
        rowData[header] = values[index] || '';
      });

      data.push({
        ...rowData,
        _rowIndex: i  // Keep original row number for error reporting
      });
    }

    return {
      success: true,
      headers,
      data,
      delimiter,
      totalRows: data.length
    };

  } catch (error) {
    return {
      success: false,
      error: error.message,
      headers: [],
      data: []
    };
  }
};

/**
 * Export data to CSV format
 * @param {Array} data - Array of objects to export
 * @param {Array} columns - Column definitions [{key, label}]
 * @returns {string} CSV formatted string
 */
export const exportToCSV = (data, columns) => {
  if (!data || data.length === 0) return '';

  // Create header row
  const headers = columns.map(col => `"${col.label || col.key}"`).join(',');
  
  // Create data rows
  const rows = data.map(row => {
    return columns.map(col => {
      const value = row[col.key] || '';
      // Escape quotes and wrap in quotes if contains comma or newline
      const escaped = String(value).replace(/"/g, '""');
      return /[,\n\r"]/.test(escaped) ? `"${escaped}"` : escaped;
    }).join(',');
  });

  return [headers, ...rows].join('\n');
};