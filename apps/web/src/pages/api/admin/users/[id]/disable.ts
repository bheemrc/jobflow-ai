import type { APIRoute } from "astro";
import { requireAdmin } from "@/lib/admin";
import { json } from "@/lib/http";

export const POST: APIRoute = async ({ request, params }) => {
  try {
    requireAdmin({ request });
  } catch (e) {
    return e as Response;
  }

  const userId = params.id || "";
  const aiBase = process.env.AI_SERVICE_URL || "http://localhost:8002";
  const res = await fetch(`${aiBase}/admin/users/${userId}/disable`, { method: "POST" });
  const data = await res.json();
  return json(data, { status: res.status });
};

export const DELETE: APIRoute = async ({ request, params }) => {
  try {
    requireAdmin({ request });
  } catch (e) {
    return e as Response;
  }

  const userId = params.id || "";
  const aiBase = process.env.AI_SERVICE_URL || "http://localhost:8002";
  const res = await fetch(`${aiBase}/admin/users/${userId}/disable`, { method: "DELETE" });
  const data = await res.json();
  return json(data, { status: res.status });
};
