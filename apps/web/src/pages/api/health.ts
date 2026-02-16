import type { APIRoute } from "astro";
import { json } from "@/lib/http";

export const GET: APIRoute = async () => {
  return json({ status: "ok" });
};
