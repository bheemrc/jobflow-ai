const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8002";

export async function searchJobs(params: Record<string, unknown>, userId?: string): Promise<unknown> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (userId) headers["X-User-Id"] = userId;
  const res = await fetch(`${AI_SERVICE_URL}/api/v1/jobs/search`, {
    method: "POST",
    headers,
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`JSearch failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function profileSearch(query: string, userId?: string): Promise<unknown> {
  const url = new URL(`${AI_SERVICE_URL}/api/v1/jobs/profile-search`);
  url.searchParams.set("query", query);
  const headers: Record<string, string> = {};
  if (userId) headers["X-User-Id"] = userId;
  const res = await fetch(url.toString(), { headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`JSearch profile-search failed (${res.status}): ${text}`);
  }
  return res.json();
}
