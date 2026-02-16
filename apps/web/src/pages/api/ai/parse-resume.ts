import type { APIRoute } from "astro";
import { json } from "@/lib/http";
import { requireUserId } from "@/lib/auth";
import { extractText } from "unpdf";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8002";

async function extractPdfText(buffer: Uint8Array): Promise<string> {
  const result = await extractText(buffer);
  return (result.text ?? []).join("\n");
}

export const POST: APIRoute = async ({ request }) => {
  let userId: string;
  try {
    userId = requireUserId({ request });
  } catch (e) {
    return e as Response;
  }

  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const pastedText = formData.get("text") as string | null;

    let resumeText = "";

    if (file && file.size > 0) {
      const buffer = new Uint8Array(await file.arrayBuffer());
      if (file.name.endsWith(".pdf") || file.type == "application/pdf") {
        resumeText = await extractPdfText(buffer);
      } else {
        resumeText = new TextDecoder().decode(buffer);
      }
    } else if (pastedText?.trim()) {
      resumeText = pastedText.trim();
    } else {
      return json({ error: "No file or text provided" }, { status: 400 });
    }

    if (!resumeText.trim()) {
      return json({ error: "Could not extract text from PDF" }, { status: 400 });
    }

    const uploadRes = await fetch(`${AI_SERVICE_URL}/resume/upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-User-Id": userId },
      body: JSON.stringify({ text: resumeText }),
    });

    if (!uploadRes.ok) {
      return json({ error: "Failed to store resume" }, { status: 500 });
    }

    const uploadData = await uploadRes.json();

    const profileRes = await fetch(`${AI_SERVICE_URL}/coach`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-User-Id": userId },
      body: JSON.stringify({
        message: `Extract a structured YAML job application profile from the following resume. Include these fields:
- name (full name)
- email
- phone
- location (city, state)
- linkedin (if present)
- github (if present)
- website (if present)
- summary (2-3 sentence professional summary)
- target_roles (list of 3-5 job titles they'd be a fit for)
- skills (list, grouped by category: languages, frameworks, tools, etc.)
- experience (list with: title, company, dates, highlights as bullet points)
- education (list with: degree, school, year)
- certifications (list, if any)

Return ONLY the YAML block, no explanation. Use valid YAML syntax.

RESUME TEXT:
${resumeText.slice(0, 4000)}`,
      }),
    });

    let yamlProfile = "";
    if (profileRes.ok) {
      const profileData = await profileRes.json();
      const raw = profileData.response || "";
      yamlProfile = raw
        .replace(/^```ya?ml\s*/i, "")
        .replace(/^```\s*/m, "")
        .replace(/\s*```\s*$/m, "")
        .trim();
    }

    return json({
      resume_id: uploadData.resume_id,
      text: resumeText,
      yaml_profile: yamlProfile,
    });
  } catch (err) {
    return json({
      error: err instanceof Error ? err.message : "Failed to process resume",
    }, { status: 500 });
  }
};
