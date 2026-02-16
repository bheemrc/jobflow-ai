import type { APIRoute } from "astro";
import { getUserId } from "@/lib/auth";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8002";

async function proxy(request: Request, params: Record<string, string | undefined>) {
  const userId = getUserId({ request });
  const path = params.path || "";
  const target = `${AI_SERVICE_URL}/${path}`;

  const headers = new Headers(request.headers);
  if (userId) headers.set("X-User-Id", userId);
  headers.delete("host");

  const init: RequestInit = {
    method: request.method,
    headers,
    body: request.method !== "GET" && request.method !== "HEAD" ? await request.arrayBuffer() : undefined,
  };

  const isStreamRequest = path.includes("stream");
  const isSlowRequest = path.includes("discover") || path.includes("coach") || path.includes("research");
  const timeoutMs = isStreamRequest ? 300_000 : isSlowRequest ? 60_000 : 30_000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  init.signal = controller.signal;

  try {
    const upstream = await fetch(target, init);
    clearTimeout(timer);
    const contentType = upstream.headers.get("Content-Type") || "";

    if (contentType.includes("text/event-stream")) {
      return new Response(upstream.body, {
        status: upstream.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
          "Connection": "keep-alive",
          "X-Accel-Buffering": "no",
        },
      });
    }

    const data = await upstream.arrayBuffer();
    return new Response(data, {
      status: upstream.status,
      headers: {
        "Content-Type": contentType || "application/json",
      },
    });
  } catch (e) {
    clearTimeout(timer);
    const message = e instanceof Error ? e.message : "AI service unavailable";
    return new Response(JSON.stringify({ error: message }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }
}

export const GET: APIRoute = async ({ request, params }) => proxy(request, params);
export const POST: APIRoute = async ({ request, params }) => proxy(request, params);
export const DELETE: APIRoute = async ({ request, params }) => proxy(request, params);
export const PATCH: APIRoute = async ({ request, params }) => proxy(request, params);
export const PUT: APIRoute = async ({ request, params }) => proxy(request, params);
