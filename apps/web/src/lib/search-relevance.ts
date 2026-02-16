import { JobResult } from "./types";

function relevanceScore(title: string, query: string): number {
  const titleLower = title.toLowerCase();
  const queryLower = query.toLowerCase();

  // Exact match
  if (titleLower === queryLower) return 4;

  const queryWords = queryLower.split(/\s+/).filter(Boolean);
  const titleWords = titleLower.split(/\s+/).filter(Boolean);

  // All query words present in title
  const allPresent = queryWords.every((w) =>
    titleWords.some((tw) => tw === w || tw.includes(w) || w.includes(tw))
  );
  if (allPresent) return 3;

  // Partial: count how many query words match
  const matchCount = queryWords.filter((w) =>
    titleWords.some((tw) => tw === w || tw.includes(w) || w.includes(tw))
  ).length;
  if (matchCount > 0) return 1 + matchCount / queryWords.length;

  // No match
  return 0;
}

export function sortByRelevance(jobs: JobResult[], query: string): JobResult[] {
  if (!query.trim()) return jobs;

  const scored = jobs.map((job, index) => ({
    job,
    score: relevanceScore(job.title, query),
    index,
  }));

  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.index - b.index; // stable: preserve original order for equal scores
  });

  return scored.map((s) => s.job);
}
