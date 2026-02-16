import type { APIRoute } from "astro";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Lightweight streaming endpoint for the Agent Arena.
 * Calls OpenAI directly (bypasses the LangGraph job-coaching pipeline).
 */

let _apiKey: string | null = null;
let _model: string = "gpt-4o";

function getConfig() {
  if (_apiKey) return { apiKey: _apiKey, model: _model };

  // 1. Check process env
  if (process.env.OPENAI_API_KEY) {
    _apiKey = process.env.OPENAI_API_KEY;
    _model = process.env.OPENAI_MODEL || "gpt-4o";
    return { apiKey: _apiKey, model: _model };
  }

  // 2. Read from backend .env
  try {
    const envPath = resolve(process.cwd(), "..", "api", ".env");
    const envContent = readFileSync(envPath, "utf-8");
    for (const line of envContent.split("\n")) {
      const trimmed = line.trim();
      if (trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const eqIdx = trimmed.indexOf("=");
      const key = trimmed.slice(0, eqIdx).trim();
      const val = trimmed.slice(eqIdx + 1).trim();
      if (key === "OPENAI_API_KEY" && val) _apiKey = val;
      if (key === "OPENAI_MODEL" && val) _model = val;
    }
  } catch {
    // .env not found
  }

  if (!_apiKey) throw new Error("OPENAI_API_KEY not configured");
  return { apiKey: _apiKey, model: _model };
}

export const POST: APIRoute = async ({ request }) => {
  let config;
  try {
    config = getConfig();
  } catch {
    return new Response(JSON.stringify({ error: "API key not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const body = await request.json();
  const { message } = body as { message: string };

  if (!message) {
    return new Response(JSON.stringify({ error: "message is required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({
        model: config.model,
        stream: true,
        max_tokens: 2048,
        temperature: 0.7,
        messages: [{ role: "user", content: message }],
      }),
    });

    if (!upstream.ok) {
      const err = await upstream.text();
      return new Response(JSON.stringify({ error: `OpenAI error: ${upstream.status}`, detail: err }), {
        status: upstream.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Transform OpenAI SSE into our simpler SSE format
    const reader = upstream.body?.getReader();
    if (!reader) {
      return new Response(JSON.stringify({ error: "No response body" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      });
    }

    const encoder = new TextEncoder();
    const decoder = new TextDecoder();

    const stream = new ReadableStream({
      async pull(controller) {
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            // Process remaining buffer
            if (buffer.trim()) {
              for (const line of buffer.split("\n")) {
                const parsed = parseLine(line);
                if (parsed) controller.enqueue(encoder.encode(parsed));
              }
            }
            controller.enqueue(encoder.encode(`data: {"type":"done"}\n\n`));
            controller.close();
            return;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const parsed = parseLine(line);
            if (parsed) controller.enqueue(encoder.encode(parsed));
          }
        }
      },
      cancel() {
        reader.cancel();
      },
    });

    return new Response(stream, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Stream failed";
    return new Response(JSON.stringify({ error: msg }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }
};

function parseLine(line: string): string | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data: ")) return null;
  const payload = trimmed.slice(6);
  if (payload === "[DONE]") return null;

  try {
    const obj = JSON.parse(payload);
    const delta = obj.choices?.[0]?.delta;
    if (delta?.content) {
      return `data: {"type":"delta","text":${JSON.stringify(delta.content)}}\n\n`;
    }
  } catch {
    // skip
  }
  return null;
}
