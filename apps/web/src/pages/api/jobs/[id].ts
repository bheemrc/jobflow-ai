import type { APIRoute } from "astro";
import { queryOne, execute } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { json } from "@/lib/http";

export const GET: APIRoute = async ({ request, params }) => {
  let userId: string;
  try {
    userId = requireUserId({ request });
  } catch (e) {
    return e as Response;
  }

  const id = params.id || "";
  const job = await queryOne("SELECT * FROM saved_jobs WHERE id = $1 AND user_id = $2", [Number(id), userId]);
  if (!job) {
    return json({ error: "Job not found" }, { status: 404 });
  }
  return json(job);
};

export const PATCH: APIRoute = async ({ request, params }) => {
  let userId: string;
  try {
    userId = requireUserId({ request });
  } catch (e) {
    return e as Response;
  }

  const id = params.id || "";
  const body = await request.json();

  const existing = await queryOne("SELECT * FROM saved_jobs WHERE id = $1 AND user_id = $2", [Number(id), userId]);
  if (!existing) {
    return json({ error: "Job not found" }, { status: 404 });
  }

  const setClauses: string[] = [];
  const values: unknown[] = [];
  let paramIdx = 1;

  if ((body as Record<string, unknown>).status !== undefined) {
    setClauses.push(`status = $${paramIdx++}`);
    values.push((body as Record<string, unknown>).status);
  }
  if ((body as Record<string, unknown>).notes !== undefined) {
    setClauses.push(`notes = $${paramIdx++}`);
    values.push((body as Record<string, unknown>).notes);
  }

  if (setClauses.length == 0) {
    return json({ error: "No fields to update" }, { status: 400 });
  }

  setClauses.push(`updated_at = NOW()`);
  values.push(Number(id));
  values.push(userId);

  const updated = await queryOne(
    `UPDATE saved_jobs SET ${setClauses.join(", ")} WHERE id = $${paramIdx++} AND user_id = $${paramIdx} RETURNING *`,
    values
  );
  return json(updated);
};

export const DELETE: APIRoute = async ({ request, params }) => {
  let userId: string;
  try {
    userId = requireUserId({ request });
  } catch (e) {
    return e as Response;
  }

  const id = params.id || "";

  const result = await execute("DELETE FROM saved_jobs WHERE id = $1 AND user_id = $2", [Number(id), userId]);
  if (result.rowCount == 0) {
    return json({ error: "Job not found" }, { status: 404 });
  }

  return json({ ok: true });
};
