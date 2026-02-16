"use client";

import { useState, useEffect, useCallback } from "react";
import { SavedJob, JobStatus } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, ExternalLink, Trash2, LayoutGrid, List, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import StatusBadge from "./status-badge";
import StatusFilter from "./status-filter";
import JobDetailModal from "./job-detail-modal";

const STATUSES: JobStatus[] = ["saved", "applied", "interview", "offer", "rejected"];

export default function JobTable() {
  const [jobs, setJobs] = useState<SavedJob[]>([]);
  const [filter, setFilter] = useState<JobStatus | "all">("all");
  const [selectedJob, setSelectedJob] = useState<SavedJob | null>(null);
  const [loading, setLoading] = useState(true);

  const view = useAppStore((s) => s.savedJobsView);
  const setView = useAppStore((s) => s.setSavedJobsView);

  useEffect(() => {
    useAppStore.persist.rehydrate();
  }, []);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const url = filter === "all" ? "/api/jobs" : `/api/jobs?status=${filter}`;
      const res = await fetch(url);
      const data = await res.json();
      if (Array.isArray(data)) setJobs(data);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  async function handleStatusChange(id: number, status: JobStatus) {
    const res = await fetch(`/api/jobs/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (res.ok) {
      const updated = await res.json();
      setJobs((prev) => prev.map((j) => (j.id === id ? updated : j)));
    }
  }

  async function handleDelete(id: number) {
    const res = await fetch(`/api/jobs/${id}`, { method: "DELETE" });
    if (res.ok) {
      setJobs((prev) => prev.filter((j) => j.id !== id));
    }
  }

  function handleModalUpdate(updated: SavedJob) {
    setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
  }

  const salary = (job: SavedJob) =>
    (job.min_amount != null && job.min_amount > 0) || (job.max_amount != null && job.max_amount > 0)
      ? [(job.min_amount != null && job.min_amount > 0) && `$${(job.min_amount / 1000).toFixed(0)}k`, (job.max_amount != null && job.max_amount > 0) && `$${(job.max_amount / 1000).toFixed(0)}k`]
          .filter(Boolean)
          .join(" - ")
      : null;

  return (
    <div className="flex h-full">
      <div className={`flex-1 overflow-y-auto transition-all ${selectedJob ? "mr-0" : ""}`}>
        <div className="p-6">
          {/* Header */}
          <div className="mb-6 flex items-center justify-between animate-fade-in-up">
            <div>
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-lg flex items-center justify-center text-[16px] bg-purple-500/10 border border-purple-500/20">
                  &#9670;
                </div>
                <div>
                  <h1 className="text-xl font-bold text-foreground">
                    Pipeline
                  </h1>
                  <p className="mt-0.5 text-[11px] font-mono text-muted-foreground">
                    {jobs.length} target{jobs.length !== 1 ? "s" : ""} tracked
                  </p>
                </div>
              </div>
            </div>
            <div className="inline-flex rounded-lg bg-muted p-1">
              <Button
                variant={view === "grid" ? "secondary" : "ghost"}
                size="icon"
                onClick={() => setView("grid")}
                className="h-8 w-8"
                title="Grid view"
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant={view === "table" ? "secondary" : "ghost"}
                size="icon"
                onClick={() => setView("table")}
                className="h-8 w-8"
                title="Table view"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="mb-5">
            <StatusFilter current={filter} onChange={setFilter} />
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <Loader2 className="h-6 w-6 animate-spin mb-3 text-primary" />
              <p className="text-sm text-muted-foreground">Loading jobs...</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl mb-4 bg-muted">
                <svg className="h-7 w-7 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
              </div>
              <p className="text-sm font-medium text-foreground">Pipeline empty</p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                {filter !== "all" ? `No targets with status "${filter}".` : "Use Discover to find jobs, then save targets to your pipeline."}
              </p>
            </div>
          ) : view === "grid" ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 stagger">
              {jobs.map((job) => (
                <Card
                  key={job.id}
                  onClick={() => setSelectedJob(job)}
                  className={cn(
                    "cursor-pointer p-5 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5",
                    selectedJob?.id === job.id && "ring-2 ring-primary"
                  )}
                >
                  <div className="relative z-10">
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div className="min-w-0">
                        <h3 className="text-[13px] font-semibold line-clamp-1 text-foreground">
                          {job.title}
                        </h3>
                        <p className="mt-0.5 text-[11px] text-muted-foreground">{job.company}</p>
                      </div>
                      <StatusBadge status={job.status} />
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 mb-3 text-[11px]">
                      {job.location && (
                        <span className="flex items-center gap-1 text-muted-foreground">
                          <MapPin className="h-3 w-3" />
                          {job.location}
                        </span>
                      )}
                      {job.is_remote && (
                        <Badge variant="success">Remote</Badge>
                      )}
                    </div>

                    <div className="flex items-center justify-between">
                      {salary(job) ? (
                        <span className="text-[11px] font-semibold font-mono text-primary">{salary(job)}</span>
                      ) : (
                        <span />
                      )}
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {new Date(job.saved_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="overflow-hidden">
              <div className="relative z-10 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Title</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Company</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Location</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Status</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Saved</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => (
                      <tr
                        key={job.id}
                        className={cn(
                          "cursor-pointer border-b transition-colors duration-150 hover:bg-accent",
                          selectedJob?.id === job.id && "bg-primary/5"
                        )}
                        onClick={() => setSelectedJob(job)}
                      >
                        <td className="px-4 py-3">
                          <span className="text-[13px] font-medium text-foreground">
                            {job.title}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[12px] text-muted-foreground">{job.company}</td>
                        <td className="px-4 py-3 text-[12px] text-muted-foreground">{job.location}</td>
                        <td className="px-4 py-3">
                          <select
                            value={job.status}
                            onChange={(e) => { e.stopPropagation(); handleStatusChange(job.id, e.target.value as JobStatus); }}
                            onClick={(e) => e.stopPropagation()}
                            className="flex h-8 rounded-lg border border-input bg-background px-2 py-1 text-[11px] capitalize ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            {STATUSES.map((s) => (
                              <option key={s} value={s}>{s}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground">
                          {new Date(job.saved_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            <Button
                              variant="ghost"
                              size="icon"
                              asChild
                              className="h-8 w-8 text-muted-foreground hover:text-primary"
                            >
                              <a
                                href={job.job_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <ExternalLink className="h-4 w-4" />
                              </a>
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDelete(job.id)}
                              className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>

      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onUpdate={handleModalUpdate}
        />
      )}
    </div>
  );
}
