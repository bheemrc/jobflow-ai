import { JobResult } from "./types";

const SENIORITY_PREFIXES = /^(senior|junior|lead|staff|principal|sr\.?|jr\.?)\s+/i;

const EQUIVALENTS: string[][] = [
  ["engineer", "developer"],
  ["frontend", "ui", "react"],
  ["backend", "server-side", "api"],
  ["fullstack", "full stack", "full-stack"],
  ["devops", "sre", "platform"],
  ["data", "analytics", "ml"],
  ["product manager", "program manager"],
];

function normalize(title: string): string {
  return title.toLowerCase().trim();
}

function stripSeniority(title: string): string {
  return title.replace(SENIORITY_PREFIXES, "").trim();
}

function swapEquivalents(title: string): string[] {
  const lower = normalize(title);
  const results: string[] = [];

  for (const group of EQUIVALENTS) {
    for (const term of group) {
      if (lower.includes(term)) {
        for (const swap of group) {
          if (swap !== term) {
            results.push(lower.replace(term, swap));
          }
        }
      }
    }
  }

  return results;
}

export function getSimilarRoles(job: JobResult): string[] {
  const original = normalize(job.title);
  const base = stripSeniority(job.title);
  const baseNorm = normalize(base);

  const suggestions = new Set<string>();

  // Base title without seniority as first suggestion
  if (baseNorm !== original) {
    suggestions.add(base);
  }

  // Swap equivalents on the original title
  for (const variant of swapEquivalents(job.title)) {
    if (normalize(variant) !== original) {
      suggestions.add(variant);
    }
  }

  // Swap equivalents on the base (seniority-stripped) title
  for (const variant of swapEquivalents(base)) {
    if (normalize(variant) !== original) {
      suggestions.add(variant);
    }
  }

  return Array.from(suggestions)
    .filter((s) => normalize(s) !== original)
    .slice(0, 4);
}

export function getRelatedSearches(
  results: JobResult[],
  currentTerm: string
): string[] {
  const current = normalize(currentTerm);
  const counts = new Map<string, number>();

  for (const job of results) {
    const title = normalize(stripSeniority(job.title));
    if (!title || title === current) continue;
    counts.set(title, (counts.get(title) || 0) + 1);
  }

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([title]) => title)
    .filter((t) => t !== current)
    .slice(0, 6);
}
