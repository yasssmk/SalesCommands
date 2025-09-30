export const dynamic = 'force-dynamic'; // évite tout cache pour cette route

export async function GET() {
  return Response.json({ ok: true });
}

export async function POST(req) {
  try {
    const ct = req.headers.get('content-type') || '';
    const body = ct.includes('json') ? await req.json() : await req.text();

    // Log minimal (évite de logguer des PII)
    const payload = typeof body === 'string' ? body : JSON.stringify(body);
    console.warn('[CSP VIOLATION]', payload.slice(0, 4000));
    return new Response(null, { status: 204 });
  } catch (err) {
    console.error('[CSP REPORT ERROR]', err);
    return Response.json({ error: 'Invalid report' }, { status: 400 });
  }
}
