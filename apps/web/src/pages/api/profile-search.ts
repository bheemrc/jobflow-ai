import type { APIRoute } from "astro";
import { profileSearch } from "@/lib/jsearch-client";
import { json } from "@/lib/http";

export const GET: APIRoute = async ({ request }) => {
  try {
    const url = new URL(request.url);
    const query = url.searchParams.get("query") || "";
    if (!query) {
      return json({ error: "query parameter required" }, { status: 400 });
    }
    const data = await profileSearch(query);
    return json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Profile search failed";
    return json({ error: message }, { status: 502 });
  }
};
