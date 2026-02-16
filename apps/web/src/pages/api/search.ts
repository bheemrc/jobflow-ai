import type { APIRoute } from "astro";
import { searchJobs } from "@/lib/jsearch-client";
import { execute } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { json } from "@/lib/http";

export const POST: APIRoute = async ({ request }) => {
  let userId: string;
  try {
    userId = requireUserId({ request });
  } catch (e) {
    return e as Response;
  }

  try {
    const body = await request.json();
    const data = await searchJobs(body, userId);

    try {
      const resultsCount = Array.isArray(data)
        ? data.length
        : ((data as Record<string, unknown>)?.jobs as unknown[] || []).length;
      await execute(
        `INSERT INTO search_history (user_id, search_term, location, is_remote, site_name, results_count)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [
          userId,
          (body as Record<string, unknown>).search_term || "",
          (body as Record<string, unknown>).location || "",
          (body as Record<string, unknown>).is_remote ?? false,
          Array.isArray((body as Record<string, unknown>).site_name)
            ? (body as Record<string, unknown>).site_name.join(",")
            : ((body as Record<string, unknown>).site_name || ""),
          resultsCount,
        ]
      );
    } catch {
      // non-blocking
    }

    return json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Search failed";
    return json({ error: message }, { status: 502 });
  }
};
