export type AuthContext = {
  request: Request;
};

function parseCookie(cookieHeader: string | null): Record<string, string> {
  if (!cookieHeader) return {};
  return cookieHeader.split(';').reduce((acc, part) => {
    const [k, v] = part.split('=');
    if (!k) return acc;
    acc[k.trim()] = decodeURIComponent((v || '').trim());
    return acc;
  }, {} as Record<string, string>);
}

export function getUserId({ request }: AuthContext): string | null {
  const header = request.headers.get('x-user-id') || request.headers.get('X-User-Id');
  if (header) return header;
  const cookies = parseCookie(request.headers.get('cookie'));
  if (cookies.user_id) return cookies.user_id;
  const fallback = import.meta.env.DEFAULT_USER_ID || process.env.DEFAULT_USER_ID || null;
  if (fallback) return fallback;
  return null;
}

export function requireUserId({ request }: AuthContext): string {
  const userId = getUserId({ request });
  if (!userId) {
    throw new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  return userId;
}
