import type { APIRoute } from "astro";
import { requireAdmin } from "@/lib/admin";
import { json } from "@/lib/http";

export const GET: APIRoute = async ({ request }) => {
  try {
    requireAdmin({ request });
  } catch (e) {
    return e as Response;
  }

  const aiBase = process.env.AI_SERVICE_URL || "http://localhost:8002";
  const res = await fetch(`${aiBase}/bots/token-usage`, {
    headers: { "Content-Type": "application/json" },
  });
  const data = await res.json();
  return json(data, { status: res.status });
};
