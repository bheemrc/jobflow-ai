import type { APIRoute } from "astro";
import { isAdmin } from "@/lib/admin";
import { json } from "@/lib/http";

export const GET: APIRoute = async ({ request }) => {
  const admin = isAdmin({ request });
  return json({ isAdmin: admin });
};
