"use client";

import { useState, useEffect, useCallback } from "react";
import { JobResult } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { getRelatedSearches } from "@/lib/role-suggestions";
import { sortByRelevance } from "@/lib/search-relevance";
import { applySorting, SortOption } from "@/lib/job-sorting";
import { applyFilters, refineResults, hasActiveFilters, extractJobTypes, extractTopLocations, DEFAULT_FILTERS, JobFilters } from "@/lib/job-filters";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { Search, MapPin, Loader2, ArrowLeft, Zap } from "lucide-react";
import JobCard from "./job-card";
import SearchJobDetail from "./search-job-detail";
import RelatedSearches from "./related-searches";
import SortDropdown from "./sort-dropdown";
import FilterPanel from "./filter-panel";

const SITES = ["indeed", "linkedin", "glassdoor", "zip_recruiter", "google"];

const SITE_ICONS: Record<string, string> = {
  indeed: "IN",
  linkedin: "Li",
  glassdoor: "GD",
  zip_recruiter: "ZR",
  google: "G",
};

const TOP_LOCATIONS = ["Remote", "New York", "San Francisco", "Seattle", "Austin", "Chicago"];

const LOCATIONS = [
  "Remote", "New York", "San Francisco", "Seattle", "Austin",
  "Chicago", "Boston", "Denver", "Los Angeles", "Portland",
  "Atlanta", "Miami", "Dallas", "Washington DC",
];

export default function SearchForm() {
  const searchTerm = useAppStore((s) => s.searchTerm);
  const setSearchTerm = useAppStore((s) => s.setSearchTerm);
  const location = useAppStore((s) => s.location);
  const setLocation = useAppStore((s) => s.setLocation);
  const sites = useAppStore((s) => s.sites);
  const setSites = useAppStore((s) => s.setSites);
  const resultsWanted = useAppStore((s) => s.resultsWanted);
  const setResultsWanted = useAppStore((s) => s.setResultsWanted);
  const isRemote = useAppStore((s) => s.isRemote);
  const setIsRemote = useAppStore((s) => s.setIsRemote);
  const hoursOld = useAppStore((s) => s.hoursOld);
  const setHoursOld = useAppStore((s) => s.setHoursOld);
  const results = useAppStore((s) => s.results);
  const setResults = useAppStore((s) => s.setResults);
  const savedUrls = useAppStore((s) => s.savedUrls);
  const addSavedUrl = useAppStore((s) => s.addSavedUrl);
  const selectedSearchJobIndex = useAppStore((s) => s.selectedSearchJobIndex);
  const setSelectedSearchJobIndex = useAppStore((s) => s.setSelectedSearchJobIndex);
  const selectedSearchJob = selectedSearchJobIndex !== null ? results[selectedSearchJobIndex] ?? null : null;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortOption>("relevance");
  const [filters, setFilters] = useState<JobFilters>(DEFAULT_FILTERS);
  const [refineQuery, setRefineQuery] = useState("");

  useEffect(() => {
    useAppStore.persist.rehydrate();
  }, []);

  const doSearch = useCallback(async (term: string, loc: string) => {
    if (!term.trim()) return;
    setLoading(true);
    setError(null);
    setSortBy("relevance");
    setFilters(DEFAULT_FILTERS);
    setRefineQuery("");
    try {
      const body: Record<string, unknown> = {
        search_term: term,
        results_wanted: useAppStore.getState().resultsWanted,
        site_name: useAppStore.getState().sites,
      };
      if (loc) body.location = loc;
      if (useAppStore.getState().isRemote) body.is_remote = true;
      if (useAppStore.getState().hoursOld) body.hours_old = useAppStore.getState().hoursOld;

      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Search failed");
      }
      const data = await res.json();
      const jobs: JobResult[] = Array.isArray(data) ? data : data.jobs ?? [];
      const sorted = sortByRelevance(jobs, term);
      setResults(sorted);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, [setResults]);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    doSearch(searchTerm, location);
  }

  async function handleSave(job: JobResult) {
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(job),
      });
      if (res.ok || res.status === 409) {
        addSavedUrl(job.job_url);
      }
    } catch {
      // silently fail
    }
  }

  function toggleSite(site: string) {
    setSites((prev) =>
      prev.includes(site) ? prev.filter((s) => s !== site) : [...prev, site]
    );
  }

  function handleClear() {
    setSearchTerm("");
    setLocation("");
    setSites(["indeed", "linkedin"]);
    setResultsWanted(20);
    setIsRemote(false);
    setHoursOld(null);
    setResults([]);
    setSelectedSearchJobIndex(null);
    setError(null);
  }

  function handleSearchRole(term: string) {
    setSearchTerm(term);
    setSelectedSearchJobIndex(null);
    doSearch(term, location);
  }

  const relatedSearches = results.length > 0
    ? getRelatedSearches(results, searchTerm)
    : [];

  const availableJobTypes = extractJobTypes(results);
  const availableLocations = extractTopLocations(results, 8);
  const filteredResults = refineResults(applyFilters(results, filters), refineQuery);
  const displayedResults = applySorting(filteredResults, sortBy, searchTerm);

  const filtersActive = hasActiveFilters(filters, refineQuery);

  function handleClearFilters() {
    setFilters(DEFAULT_FILTERS);
    setRefineQuery("");
  }

  function handleSelectJob(displayedIndex: number) {
    const job = displayedResults[displayedIndex];
    const originalIndex = results.findIndex((r) => r.job_url === job.job_url);
    setSelectedSearchJobIndex(originalIndex);
  }

  return (
    <div className="flex h-full">
      {/* Left -- sticky filters panel */}
      <div className="w-[300px] shrink-0 relative bg-card border-r">
        <div className="sticky top-0 flex h-full flex-col overflow-y-auto relative z-10">
          {/* Header */}
          <div className="px-5 pt-5 pb-4 border-b">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl flex items-center justify-center text-[15px] bg-primary/10 border border-primary/20">
                <Zap className="h-4 w-4 text-primary" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-foreground">
                  Discover
                </h1>
                <p className="text-[10px] font-mono text-muted-foreground/70">
                  Searching {SITES.length} job boards
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSearch} className="flex flex-1 flex-col px-5 pt-4 pb-5">
            {/* Keywords */}
            <div className="mb-5">
              <label className="mb-1.5 block text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                Keywords
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Job title, skills..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="rounded-xl pl-9 pr-3 py-2.5 text-sm h-auto"
                />
              </div>
            </div>

            {/* Location */}
            <div className="mb-5">
              <label className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                Location
              </label>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {TOP_LOCATIONS.map((loc) => (
                  <button
                    key={loc}
                    type="button"
                    onClick={() => setLocation(location === loc ? "" : loc)}
                    className={cn(
                      "rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all duration-200 border",
                      location === loc
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-muted text-muted-foreground border-border hover:border-primary/50 hover:text-foreground"
                    )}
                  >
                    {loc === "Remote" && (
                      <span className="inline-block mr-1 text-[9px]">&#127760;</span>
                    )}
                    {loc}
                  </button>
                ))}
                {LOCATIONS.filter((l) => !TOP_LOCATIONS.includes(l)).some((l) => l === location) && (
                  <button
                    type="button"
                    onClick={() => setLocation("")}
                    className="rounded-lg px-2.5 py-1 text-[11px] font-medium bg-primary text-primary-foreground border border-primary shadow-sm"
                  >
                    {location}
                  </button>
                )}
              </div>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Type any city..."
                  value={LOCATIONS.includes(location) ? "" : location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="rounded-lg pl-8 pr-3 py-1.5 text-[12px] h-auto"
                />
              </div>
            </div>

            {/* Divider */}
            <Separator className="mb-5" />

            {/* Job Boards */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-2">
                <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                  Boards
                </label>
                <span className="text-[10px] font-mono text-muted-foreground/70">
                  {sites.length}/{SITES.length}
                </span>
              </div>
              <div className="grid grid-cols-5 gap-1.5">
                {SITES.map((site) => {
                  const active = sites.includes(site);
                  return (
                    <button
                      key={site}
                      type="button"
                      onClick={() => toggleSite(site)}
                      className={cn(
                        "flex flex-col items-center gap-1 rounded-lg py-2 px-1 transition-all duration-200 border",
                        active
                          ? "bg-primary/10 border-primary/30"
                          : "bg-muted border-border hover:border-primary/20"
                      )}
                      title={site.replace("_", " ")}
                    >
                      <span
                        className={cn(
                          "text-[10px] font-bold font-mono",
                          active ? "text-primary" : "text-muted-foreground"
                        )}
                      >
                        {SITE_ICONS[site]}
                      </span>
                      <span
                        className={cn(
                          "text-[8px] font-medium leading-none",
                          active ? "text-primary" : "text-muted-foreground"
                        )}
                      >
                        {site === "zip_recruiter" ? "zip" : site.slice(0, 6)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Options row */}
            <div className="mb-5">
              <label className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                Options
              </label>
              <div className="rounded-xl overflow-hidden border bg-muted">
                <div className="flex border-b">
                  <div className="flex-1 px-3 py-2.5 border-r">
                    <span className="block text-[9px] font-semibold uppercase tracking-wider mb-1 text-muted-foreground">
                      Posted
                    </span>
                    <select
                      value={hoursOld ?? ""}
                      onChange={(e) => setHoursOld(e.target.value ? Number(e.target.value) : null)}
                      className="w-full bg-transparent text-[12px] font-medium border-none outline-none p-0 appearance-none cursor-pointer text-foreground"
                    >
                      <option value="">Any time</option>
                      <option value="24">Past 24h</option>
                      <option value="72">Past 3 days</option>
                      <option value="168">Past week</option>
                      <option value="720">Past month</option>
                    </select>
                  </div>
                  <div className="flex-1 px-3 py-2.5">
                    <span className="block text-[9px] font-semibold uppercase tracking-wider mb-1 text-muted-foreground">
                      Results
                    </span>
                    <select
                      value={resultsWanted}
                      onChange={(e) => setResultsWanted(Number(e.target.value))}
                      className="w-full bg-transparent text-[12px] font-medium border-none outline-none p-0 appearance-none cursor-pointer text-foreground"
                    >
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                      <option value={50}>50</option>
                    </select>
                  </div>
                </div>
                <label className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer transition-colors duration-200 hover:bg-accent">
                  <Checkbox
                    checked={isRemote}
                    onCheckedChange={(checked) => setIsRemote(checked === true)}
                    className="h-4 w-4"
                  />
                  <span className={cn(
                    "text-[12px] font-medium",
                    isRemote ? "text-foreground" : "text-muted-foreground"
                  )}>
                    Remote only
                  </span>
                  {isRemote && (
                    <span className="ml-auto text-[9px] font-bold uppercase tracking-wider text-primary">
                      ON
                    </span>
                  )}
                </label>
              </div>
            </div>

            {/* Search button */}
            <div className="mt-auto pt-3 flex flex-col gap-2">
              <Button
                type="submit"
                disabled={loading || !searchTerm.trim()}
                className="w-full rounded-xl py-3 text-[13px] font-bold h-auto"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Scanning boards...
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <Search className="h-4 w-4" />
                    Search Jobs
                  </span>
                )}
              </Button>
              {(searchTerm || location || results.length > 0 || isRemote || hoursOld) && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleClear}
                  className="w-full rounded-xl py-2 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                >
                  Clear all
                </Button>
              )}
            </div>
          </form>
        </div>
      </div>

      {/* Right -- scrollable results */}
      <div className="flex-1 flex flex-col overflow-hidden bg-background">
        {error && (
          <div className="m-6 rounded-xl p-4 text-sm bg-destructive/10 border border-destructive/20 text-destructive">
            {error}
          </div>
        )}

        {results.length === 0 && !loading && !error && (
          <div className="flex h-full flex-col items-center justify-center px-6 animate-fade-in">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl mb-4 bg-primary/10 border border-primary/10">
              <Zap className="h-6 w-6 text-primary" />
            </div>
            <h2 className="text-lg font-semibold mb-1 text-foreground">
              Start Searching
            </h2>
            <p className="text-sm text-center max-w-sm text-muted-foreground">
              Enter keywords and location to search across multiple job boards simultaneously.
            </p>
          </div>
        )}

        {loading && results.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center animate-fade-in">
            <Loader2 className="h-8 w-8 animate-spin mb-4 text-primary" />
            <p className="text-sm font-medium text-foreground">
              Searching...
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              Searching across {sites.length} job boards
            </p>
          </div>
        )}

        {results.length > 0 && (
          <>
            {/* Results header */}
            <div className="px-6 pt-6 pb-3 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-foreground">
                  Results
                </h2>
                <Badge variant="info">
                  {filtersActive ? `${displayedResults.length} / ${results.length}` : results.length}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <SortDropdown value={sortBy} onChange={setSortBy} />
                {selectedSearchJob && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedSearchJobIndex(null)}
                    className="gap-1 text-[11px]"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Back to grid
                  </Button>
                )}
              </div>
            </div>

            {/* Filter bar */}
            <FilterPanel
              filters={filters}
              availableJobTypes={availableJobTypes}
              availableLocations={availableLocations}
              onFilterChange={setFilters}
              refineQuery={refineQuery}
              onRefineChange={setRefineQuery}
              hasActive={filtersActive}
              onClear={handleClearFilters}
            />

            {/* Content area */}
            <div className="flex-1 overflow-hidden">
              {selectedSearchJob ? (
                <div className="flex h-full">
                  {/* Compact list */}
                  <div className="w-[300px] shrink-0 overflow-y-auto bg-card border-r">
                    {displayedResults.map((job, i) => {
                      const originalIndex = results.findIndex((r) => r.job_url === job.job_url);
                      const isSelected = originalIndex === selectedSearchJobIndex;
                      const jobSalary =
                        (job.min_amount != null && job.min_amount > 0) || (job.max_amount != null && job.max_amount > 0)
                          ? [
                              (job.min_amount != null && job.min_amount > 0) && `$${(job.min_amount / 1000).toFixed(0)}k`,
                              (job.max_amount != null && job.max_amount > 0) && `$${(job.max_amount / 1000).toFixed(0)}k`,
                            ]
                              .filter(Boolean)
                              .join(" - ")
                          : null;
                      return (
                        <button
                          key={i}
                          onClick={() => handleSelectJob(i)}
                          className={cn(
                            "w-full text-left px-4 py-3 transition-colors duration-150 border-b",
                            isSelected
                              ? "bg-primary/5 border-l-2 border-l-primary"
                              : "border-l-2 border-l-transparent hover:bg-accent"
                          )}
                        >
                          <p className="text-[13px] font-medium line-clamp-1 text-foreground">
                            {job.title}
                          </p>
                          <p className="mt-0.5 text-[11px] line-clamp-1 text-muted-foreground">
                            {job.company} &middot; {job.location}
                          </p>
                          <div className="mt-1 flex items-center gap-1.5 text-[11px]">
                            {jobSalary && (
                              <span className="font-semibold font-mono text-foreground">
                                {jobSalary}
                              </span>
                            )}
                            {job.is_remote && (
                              <Badge variant="success" className="text-[10px] py-0 h-auto">
                                Remote
                              </Badge>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  {/* Detail panel */}
                  <div className="flex-1 overflow-y-auto bg-background">
                    <SearchJobDetail
                      job={selectedSearchJob}
                      onClose={() => setSelectedSearchJobIndex(null)}
                      onSave={handleSave}
                      isSaved={savedUrls.includes(selectedSearchJob.job_url)}
                      onSearchRole={handleSearchRole}
                    />
                  </div>
                </div>
              ) : (
                <div className="overflow-y-auto h-full px-6 pb-6">
                  <div className="grid gap-4 xl:grid-cols-2 stagger">
                    {displayedResults.map((job, i) => (
                      <JobCard
                        key={i}
                        job={job}
                        onSave={handleSave}
                        isSaved={savedUrls.includes(job.job_url)}
                        onClick={() => handleSelectJob(i)}
                      />
                    ))}
                  </div>
                  <RelatedSearches
                    suggestions={relatedSearches}
                    onSearch={handleSearchRole}
                  />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
