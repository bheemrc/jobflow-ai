import type { APIRoute } from "astro";
import { query, queryOne } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { json } from "@/lib/http";

export const GET: APIRoute = async ({ request }) => {
  let userId: string;
  try {
    userId = requireUserId({ request });
  } catch (e) {
    return e as Response;
  }

  const url = new URL(request.url);
  const status = url.searchParams.get("status");

  const jobs = status && status !== "all"
    ? await query("SELECT * FROM saved_jobs WHERE user_id = $1 AND status = $2 ORDER BY saved_at DESC", [userId, status])
    : await query("SELECT * FROM saved_jobs WHERE user_id = $1 ORDER BY saved_at DESC", [userId]);

  return json(jobs);
};

export const POST: APIRoute = async ({ request }) => {
  let userId: string;
  try {
    userId = requireUserId({ request });
  } catch (e) {
    return e as Response;
  }

  const body = await request.json();

  const existing = await queryOne("SELECT id FROM saved_jobs WHERE user_id = $1 AND job_url = $2", [userId, (body as Record<string, unknown>).job_url]);
  if (existing) {
    return json({ error: "Job already saved" }, { status: 409 });
  }

  const saved = await queryOne(
    `INSERT INTO saved_jobs (user_id, title, company, location, min_amount, max_amount, currency, job_url, date_posted, job_type, is_remote, description, site)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
     RETURNING *`,
    [
      userId,
      (body as Record<string, unknown>).title || "",
      (body as Record<string, unknown>).company || "",
      (body as Record<string, unknown>).location || "",
      (body as Record<string, unknown>).min_amount ?? null,
      (body as Record<string, unknown>).max_amount ?? null,
      (body as Record<string, unknown>).currency ?? null,
      (body as Record<string, unknown>).job_url,
      (body as Record<string, unknown>).date_posted ?? null,
      (body as Record<string, unknown>).job_type ?? null,
      (body as Record<string, unknown>).is_remote ?? false,
      (body as Record<string, unknown>).description ?? null,
      (body as Record<string, unknown>).site ?? null,
    ]
  );

  const aiBase = process.env.AI_SERVICE_URL || "http://localhost:8002";
  fetch(`${aiBase}/bots/event/job_saved`, { method: "POST" }).catch(() => {});

  return json(saved, { status: 201 });
};
