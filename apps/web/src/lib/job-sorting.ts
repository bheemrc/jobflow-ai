import { JobResult } from "./types";
import { sortByRelevance } from "./search-relevance";

export type SortOption = "relevance" | "date" | "salary" | "location";

function sortByDate(jobs: JobResult[]): JobResult[] {
  return [...jobs].sort((a, b) => {
    if (!a.date_posted && !b.date_posted) return 0;
    if (!a.date_posted) return 1;
    if (!b.date_posted) return -1;
    return new Date(b.date_posted).getTime() - new Date(a.date_posted).getTime();
  });
}

function sortBySalary(jobs: JobResult[]): JobResult[] {
  return [...jobs].sort((a, b) => {
    const salaryA = a.max_amount ?? a.min_amount;
    const salaryB = b.max_amount ?? b.min_amount;
    if (salaryA == null && salaryB == null) return 0;
    if (salaryA == null) return 1;
    if (salaryB == null) return -1;
    return salaryB - salaryA;
  });
}

function sortByLocation(jobs: JobResult[]): JobResult[] {
  return [...jobs].sort((a, b) => a.location.localeCompare(b.location));
}

export function applySorting(
  jobs: JobResult[],
  sortBy: SortOption,
  searchQuery: string
): JobResult[] {
  switch (sortBy) {
    case "relevance":
      return sortByRelevance(jobs, searchQuery);
    case "date":
      return sortByDate(jobs);
    case "salary":
      return sortBySalary(jobs);
    case "location":
      return sortByLocation(jobs);
    default:
      return jobs;
  }
}
