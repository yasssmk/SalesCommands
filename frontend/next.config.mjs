/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    // CSP en Report-Only pour observer sans casser l'app.
    // On garde 'unsafe-inline' (Next & libs tierces), et on log les violations.
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com data:",
      "img-src 'self' data: https:",
      "connect-src 'self' http://localhost:8000",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "report-uri /api/csp-report"
    ].join('; ');

    const baseSecurityHeaders = [
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'Content-Security-Policy-Report-Only', value: csp },
      { 
        key: 'Permissions-Policy', 
        value: 'geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=()'
      },
    ];

    return [
      {
        // Applique à tout le site Next (pages statiques & API Next)
        source: '/(.*)',
        headers: baseSecurityHeaders,
      },
    ];
  },
};

export default nextConfig;
