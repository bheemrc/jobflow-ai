import { getUserId, type AuthContext } from "./auth";

export function requireAdmin(ctx: AuthContext): string {
  const userId = getUserId(ctx);
  if (!userId) {
    throw new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  const adminIds = (import.meta.env.ADMIN_USER_IDS || process.env.ADMIN_USER_IDS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (!adminIds.includes(userId)) {
    throw new Response(JSON.stringify({ error: 'Forbidden' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  return userId;
}

export function isAdmin(ctx: AuthContext): boolean {
  const userId = getUserId(ctx);
  if (!userId) return false;
  const adminIds = (import.meta.env.ADMIN_USER_IDS || process.env.ADMIN_USER_IDS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return adminIds.includes(userId);
}
