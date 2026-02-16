import type { APIRoute } from "astro";
import { requireAdmin } from "@/lib/admin";
import { json } from "@/lib/http";

export const GET: APIRoute = async ({ request, params }) => {
  try {
    requireAdmin({ request });
  } catch (e) {
    return e as Response;
  }

  const userId = params.id || "";
  const aiBase = process.env.AI_SERVICE_URL || "http://localhost:8002";
  const res = await fetch(`${aiBase}/bots/token-usage?user_id=${encodeURIComponent(userId)}`);
  const data = await res.json();
  return json(data, { status: res.status });
};
