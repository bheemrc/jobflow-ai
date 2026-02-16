export function json(data: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers || {});
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return new Response(JSON.stringify(data), { ...init, headers });
}
