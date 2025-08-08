import DOMPurify from 'dompurify';

const sqlInjectionPatterns = [
    /(\b)(select|insert|update|delete|drop|union)(\b)/gi,
    /'(\s|\+)*or(\s|\+)*'1'(\s|\+)*=(\s|\+)*'1'/gi,
    /--(\s|\+)/g,
];

export const sanitizeInput = (data) => {
    // Skip sanitization for certain safe operations
    if (
        typeof data === 'boolean' ||
        typeof data === 'number' ||
        data === null ||
        data === undefined
    ) {
        return data;
    }

    if (typeof data === 'string') {
        // Skip sanitization for known safe patterns (like URLs, dates, etc.)
        if (data.match(/^(https?:\/\/|\/api\/|\/assets\/)/i)) {
            return data;
        }
        
        let cleaned = data;
        sqlInjectionPatterns.forEach(pattern => {
            cleaned = cleaned.replace(pattern, '');
        });
        
        return DOMPurify.sanitize(cleaned, {
            ALLOWED_TAGS: [],
            ALLOWED_ATTR: []
        }).trim();
    }

    if (Array.isArray(data)) {
        return data.map(item => sanitizeInput(item));
    }

    if (typeof data === 'object') {
        return Object.keys(data).reduce((acc, key) => {
            acc[key] = sanitizeInput(data[key]);
            return acc;
        }, {});
    }

    return data;
};

export const sanitizeApiCall = (apiFunction) => {
    return async (...args) => {
        // Only sanitize POST/PUT/PATCH request data
        const sanitizedArgs = args.map(arg => 
            typeof arg === 'object' && !Array.isArray(arg) ? sanitizeInput(arg) : arg
        );
        try {
            return await apiFunction(...sanitizedArgs);
        } catch (error) {
            // console.error('API call failed:', error);
            throw error;
        }
    };
};