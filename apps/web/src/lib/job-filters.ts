import { JobResult } from "./types";

export interface JobFilters {
  remoteOnly: boolean;
  hasSalary: boolean;
  jobTypes: string[];
  locations: string[];
}

export const DEFAULT_FILTERS: JobFilters = {
  remoteOnly: false,
  hasSalary: false,
  jobTypes: [],
  locations: [],
};

export function applyFilters(jobs: JobResult[], filters: JobFilters): JobResult[] {
  return jobs.filter((job) => {
    if (filters.remoteOnly && !job.is_remote) return false;
    if (filters.hasSalary && job.min_amount == null && job.max_amount == null) return false;
    if (filters.jobTypes.length > 0 && (!job.job_type || !filters.jobTypes.includes(job.job_type))) return false;
    if (filters.locations.length > 0 && !filters.locations.includes(job.location)) return false;
    return true;
  });
}

export function hasActiveFilters(filters: JobFilters, refineQuery: string): boolean {
  return (
    filters.remoteOnly ||
    filters.hasSalary ||
    filters.jobTypes.length > 0 ||
    filters.locations.length > 0 ||
    refineQuery.trim().length > 0
  );
}

export function refineResults(jobs: JobResult[], query: string): JobResult[] {
  const q = query.trim().toLowerCase();
  if (!q) return jobs;
  const words = q.split(/\s+/);
  return jobs.filter((job) => {
    const haystack = [job.title, job.company, job.location, job.description ?? ""]
      .join(" ")
      .toLowerCase();
    return words.every((w) => haystack.includes(w));
  });
}

export function extractJobTypes(jobs: JobResult[]): string[] {
  const types = new Set<string>();
  for (const job of jobs) {
    if (job.job_type) types.add(job.job_type);
  }
  return Array.from(types).sort();
}

export function extractTopLocations(jobs: JobResult[], limit = 8): string[] {
  const counts = new Map<string, number>();
  for (const job of jobs) {
    if (job.location) {
      counts.set(job.location, (counts.get(job.location) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([loc]) => loc);
}
