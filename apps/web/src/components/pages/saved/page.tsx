"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { SavedJob, JobStatus, PipelineJob } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import StatusBadge from "@/components/status-badge";
import StatusFilter from "@/components/status-filter";
import JobDetailModal from "@/components/job-detail-modal";
import ResumeUpload from "@/components/resume-upload";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const STATUSES: JobStatus[] = ["saved", "applied", "interview", "offer", "rejected"];

type TabKey = "all" | "pipeline" | "status";

const STAGES: { key: JobStatus; label: string; color: string }[] = [
  { key: "saved", label: "Saved", color: "bg-gray-500" },
  { key: "applied", label: "Applied", color: "bg-blue-400" },
  { key: "interview", label: "Interview", color: "bg-green-400" },
  { key: "offer", label: "Offer", color: "bg-yellow-400" },
  { key: "rejected", label: "Rejected", color: "bg-red-400" },
];

const STAGE_BORDER_COLORS: Record<string, string> = {
  saved: "border-gray-500",
  applied: "border-blue-400",
  interview: "border-green-400",
  offer: "border-yellow-400",
  rejected: "border-red-400",
};

export default function SavedPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-full">
        <svg className="h-6 w-6 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    }>
      <SavedPageInner />
    </Suspense>
  );
}

function SavedPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Determine initial tab from URL
  const viewParam = searchParams.get("view");
  const initialTab: TabKey = viewParam === "pipeline" ? "pipeline" : viewParam === "status" ? "status" : "all";

  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [jobs, setJobs] = useState<SavedJob[]>([]);
  const [pipeline, setPipeline] = useState<Record<string, PipelineJob[]>>({});
  const [filter, setFilter] = useState<JobStatus | "all">("all");
  const [selectedJob, setSelectedJob] = useState<SavedJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [showResumeUpload, setShowResumeUpload] = useState(false);

  const view = useAppStore((s) => s.savedJobsView);
  const setView = useAppStore((s) => s.setSavedJobsView);
  const storeResumeId = useAppStore((s) => s.resumeId);
  const setStoreResumeId = useAppStore((s) => s.setResumeId);

  useEffect(() => {
    useAppStore.persist.rehydrate();
  }, []);

  // Check for resume
  useEffect(() => {
    const stored = useAppStore.getState().resumeId;
    if (stored) {
      setResumeId(stored);
    } else {
      fetch("/api/ai/resumes")
        .then((r) => r.json())
        .then((data) => {
          if (data.resumes?.length) {
            setResumeId(data.resumes[0]);
            setStoreResumeId(data.resumes[0]);
          }
        })
        .catch(() => {});
    }
  }, [setStoreResumeId]);

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

  const fetchPipeline = useCallback(async () => {
    try {
      const res = await fetch("/api/ai/jobs/pipeline");
      const data = await res.json();
      if (data && typeof data === "object") setPipeline(data);
    } catch {}
  }, []);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);
  useEffect(() => { if (activeTab === "pipeline") fetchPipeline(); }, [activeTab, fetchPipeline]);

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

  async function moveJob(jobId: number, newStatus: string) {
    await fetch(`/api/ai/jobs/${jobId}/stage`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    fetchPipeline();
    fetchJobs();
  }

  function handlePrepare(job: SavedJob) {
    const params = new URLSearchParams();
    params.set("company", job.company);
    params.set("role", job.title);
    params.set("job_id", String(job.id));
    params.set("source", "saved_job");
    router.push(`/ai?${params.toString()}`);
  }

  function handleResumeUploaded(id: string) {
    setResumeId(id);
    setStoreResumeId(id);
    setShowResumeUpload(false);
  }

  const salary = (job: SavedJob) =>
    (job.min_amount != null && job.min_amount > 0) || (job.max_amount != null && job.max_amount > 0)
      ? [(job.min_amount != null && job.min_amount > 0) && `$${(job.min_amount / 1000).toFixed(0)}k`, (job.max_amount != null && job.max_amount > 0) && `$${(job.max_amount / 1000).toFixed(0)}k`]
          .filter(Boolean)
          .join(" - ")
      : null;

  // Stats
  const stats = {
    total: jobs.length,
    saved: jobs.filter((j) => j.status === "saved").length,
    applied: jobs.filter((j) => j.status === "applied").length,
    interview: jobs.filter((j) => j.status === "interview").length,
    offer: jobs.filter((j) => j.status === "offer").length,
  };

  const tabs: { key: TabKey; label: string }[] = [
    { key: "all", label: "All Jobs" },
    { key: "pipeline", label: "Pipeline" },
    { key: "status", label: "By Status" },
  ];

  return (
    <div className="flex h-full">
      <div className={`flex-1 overflow-y-auto transition-all ${selectedJob ? "mr-0" : ""}`}>
        <div className="p-6">
          {/* Header */}
          <div className="mb-5 animate-fade-in-up">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-xl font-bold text-foreground">My Jobs</h1>
                <p className="mt-1 text-[12px] data-mono text-muted-foreground/70">
                  Your job search command center
                </p>
              </div>
              <div className="flex items-center gap-2">
                {resumeId ? (
                  <Badge variant="success">
                    <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Resume loaded
                  </Badge>
                ) : (
                  <Badge
                    variant="warning"
                    className="cursor-pointer transition-all duration-200 border border-yellow-400/20"
                    onClick={() => setShowResumeUpload(true)}
                  >
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                    </svg>
                    Upload Resume
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* Resume upload banner */}
          {showResumeUpload && !resumeId && (
            <Card className="mb-5 p-5 animate-fade-in-up border-yellow-400/20">
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Upload Your Resume</h3>
                    <p className="text-[11px] mt-0.5 text-muted-foreground/70">
                      Unlock AI-powered job matching, resume tailoring, and interview prep
                    </p>
                  </div>
                  <button
                    onClick={() => setShowResumeUpload(false)}
                    className="rounded-lg p-1 transition-colors text-muted-foreground hover:text-foreground"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="max-w-md">
                  <ResumeUpload onResumeId={handleResumeUploaded} />
                </div>
              </div>
            </Card>
          )}

          {/* Stats row */}
          <div className="grid grid-cols-5 gap-3 mb-5 stagger">
            {[
              { label: "Total", value: stats.total, color: "text-foreground" },
              { label: "Saved", value: stats.saved, color: "text-gray-500" },
              { label: "Applied", value: stats.applied, color: "text-blue-400" },
              { label: "Interviewing", value: stats.interview, color: "text-green-400" },
              { label: "Offers", value: stats.offer, color: "text-yellow-400" },
            ].map((stat) => (
              <Card key={stat.label} className="p-3">
                <div className="relative z-10">
                  <p className={cn("data-mono text-lg font-bold", stat.color)}>{stat.value}</p>
                  <p className="text-[10px] font-medium text-muted-foreground/70">{stat.label}</p>
                </div>
              </Card>
            ))}
          </div>

          {/* Tab bar */}
          <div className="flex items-center justify-between mb-5">
            <TabsList>
              {tabs.map((tab) => (
                <TabsTrigger
                  key={tab.key}
                  value={tab.key}
                  data-state={activeTab === tab.key ? "active" : "inactive"}
                  onClick={() => setActiveTab(tab.key)}
                  className="text-[12px]"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {activeTab === "all" && (
              <div className="inline-flex rounded-lg p-1 bg-muted">
                <button
                  onClick={() => setView("grid")}
                  className={cn(
                    "rounded-md p-1.5 transition-all duration-200",
                    view === "grid" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
                  )}
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
                  </svg>
                </button>
                <button
                  onClick={() => setView("table")}
                  className={cn(
                    "rounded-md p-1.5 transition-all duration-200",
                    view === "table" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
                  )}
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
                  </svg>
                </button>
              </div>
            )}
          </div>

          {/* Tab content */}
          {activeTab === "all" && (
            <AllJobsTab
              jobs={jobs}
              loading={loading}
              filter={filter}
              setFilter={setFilter}
              view={view}
              selectedJob={selectedJob}
              setSelectedJob={setSelectedJob}
              handleStatusChange={handleStatusChange}
              handleDelete={handleDelete}
              handlePrepare={handlePrepare}
              salary={salary}
              resumeId={resumeId}
            />
          )}

          {activeTab === "pipeline" && (
            <PipelineTab pipeline={pipeline} moveJob={moveJob} handlePrepare={(job: PipelineJob) => {
              handlePrepare({ ...job, notes: "", description: null, date_posted: null, job_type: null, is_remote: false, currency: null, site: null, min_amount: job.min_amount ?? null, max_amount: job.max_amount ?? null } as SavedJob);
            }} />
          )}

          {activeTab === "status" && (
            <ByStatusTab jobs={jobs} loading={loading} setSelectedJob={setSelectedJob} salary={salary} handlePrepare={handlePrepare} />
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

// --- ALL JOBS TAB ---

function AllJobsTab({
  jobs, loading, filter, setFilter, view, selectedJob, setSelectedJob,
  handleStatusChange, handleDelete, handlePrepare, salary, resumeId,
}: {
  jobs: SavedJob[];
  loading: boolean;
  filter: JobStatus | "all";
  setFilter: (f: JobStatus | "all") => void;
  view: "grid" | "table";
  selectedJob: SavedJob | null;
  setSelectedJob: (j: SavedJob | null) => void;
  handleStatusChange: (id: number, status: JobStatus) => void;
  handleDelete: (id: number) => void;
  handlePrepare: (job: SavedJob) => void;
  salary: (job: SavedJob) => string | null;
  resumeId: string | null;
}) {
  return (
    <>
      <div className="mb-5">
        <StatusFilter current={filter} onChange={setFilter} />
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <svg className="h-6 w-6 animate-spin mb-3 text-primary" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm text-muted-foreground/70">Loading jobs...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl mb-4 bg-muted">
            <svg className="h-8 w-8 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
          </div>
          <p className="text-sm font-medium text-foreground">No saved jobs yet</p>
          <p className="mt-1 text-[12px] text-center max-w-xs text-muted-foreground/70">
            {filter !== "all"
              ? `No jobs with status "${filter}".`
              : "Search for jobs and save the ones you're interested in. AI agents will help you prepare for each one."}
          </p>
          <Button asChild className="mt-4 rounded-xl px-5 py-2.5 text-[12px]">
            <a href="/search">Search Jobs</a>
          </Button>
        </div>
      ) : view === "grid" ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 stagger">
          {jobs.map((job) => (
            <Card
              key={job.id}
              className={cn(
                "cursor-pointer p-5 group transition-colors hover:bg-accent/50",
                selectedJob?.id === job.id && "ring-2 ring-primary",
              )}
              onClick={() => setSelectedJob(job)}
            >
              <div className="relative z-10">
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="min-w-0">
                    <h3 className="text-[13px] font-semibold line-clamp-1 text-foreground">
                      {job.title}
                    </h3>
                    <p className="mt-0.5 text-[11px] text-muted-foreground/70">{job.company}</p>
                  </div>
                  <StatusBadge status={job.status} />
                </div>

                <div className="flex flex-wrap items-center gap-1.5 mb-3 text-[11px]">
                  {job.location && (
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <svg className="h-3 w-3 text-muted-foreground/70" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                      </svg>
                      {job.location}
                    </span>
                  )}
                  {job.is_remote && (
                    <Badge variant="success">Remote</Badge>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  {salary(job) ? (
                    <span className="text-[11px] font-semibold data-mono text-primary">{salary(job)}</span>
                  ) : (
                    <span />
                  )}
                  <span className="data-mono text-[10px] text-muted-foreground/70">
                    {new Date(job.saved_at).toLocaleDateString()}
                  </span>
                </div>

                {/* AI Prepare button */}
                {resumeId && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); handlePrepare(job); }}
                    className="mt-3 w-full rounded-lg py-1.5 text-[11px] font-medium opacity-0 group-hover:opacity-100 transition-all duration-200 text-primary border-primary/20 hover:bg-primary hover:text-primary-foreground"
                  >
                    <span className="flex items-center justify-center gap-1.5">
                      <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                      </svg>
                      Prepare with AI
                    </span>
                  </Button>
                )}
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
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Title</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Company</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Location</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Saved</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className={cn(
                      "cursor-pointer transition-colors duration-150 border-b border-border/50 hover:bg-accent",
                      selectedJob?.id === job.id && "bg-primary/5",
                    )}
                    onClick={() => setSelectedJob(job)}
                  >
                    <td className="px-4 py-3">
                      <span className="text-[13px] font-medium text-foreground">{job.title}</span>
                    </td>
                    <td className="px-4 py-3 text-[12px] text-muted-foreground">{job.company}</td>
                    <td className="px-4 py-3 text-[12px] text-muted-foreground/70">{job.location}</td>
                    <td className="px-4 py-3">
                      <select
                        value={job.status}
                        onChange={(e) => { e.stopPropagation(); handleStatusChange(job.id, e.target.value as JobStatus); }}
                        onClick={(e) => e.stopPropagation()}
                        className="flex h-8 rounded-md border border-input bg-background px-2 py-1 text-[11px] capitalize ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
                      </select>
                    </td>
                    <td className="px-4 py-3 data-mono text-[11px] text-muted-foreground/70">
                      {new Date(job.saved_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        {resumeId && (
                          <button
                            onClick={() => handlePrepare(job)}
                            className="rounded-lg px-2 py-1 text-[10px] font-medium transition-colors duration-200 text-primary bg-primary/10 hover:bg-primary/20"
                            title="Prepare with AI"
                          >
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                            </svg>
                          </button>
                        )}
                        <a
                          href={job.job_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-lg p-1.5 transition-colors duration-200 text-muted-foreground hover:text-primary"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                          </svg>
                        </a>
                        <button
                          onClick={() => handleDelete(job.id)}
                          className="rounded-lg p-1.5 transition-colors duration-200 text-muted-foreground hover:text-destructive"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}

// --- PIPELINE TAB ---

function PipelineTab({
  pipeline, moveJob, handlePrepare,
}: {
  pipeline: Record<string, PipelineJob[]>;
  moveJob: (id: number, status: string) => void;
  handlePrepare: (job: PipelineJob) => void;
}) {
  return (
    <div className="grid grid-cols-5 gap-4 stagger">
      {STAGES.map((stage) => {
        const jobs = pipeline[stage.key] || [];
        return (
          <div key={stage.key}>
            <div className={cn("mb-3 pb-2 border-b-2", STAGE_BORDER_COLORS[stage.key])}>
              <div className="flex items-center justify-between">
                <h3 className="text-[13px] font-semibold text-foreground">
                  {stage.label}
                </h3>
                <span className="data-mono text-[11px] text-muted-foreground/70">
                  {jobs.length}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              {jobs.map((job) => (
                <Card key={job.id} className="p-3 group hover:bg-accent/50 transition-colors">
                  <div className="relative z-10">
                    <p className="text-[12px] font-medium truncate text-foreground">{job.title}</p>
                    <p className="text-[11px] truncate text-muted-foreground/70">{job.company}</p>
                    <p className="text-[10px] mt-1 text-muted-foreground/70">{job.location}</p>
                    {job.min_amount && job.max_amount && (
                      <p className="data-mono text-[10px] mt-0.5 text-primary">
                        ${job.min_amount.toLocaleString()} - ${job.max_amount.toLocaleString()}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      {STAGES.filter((s) => s.key !== stage.key).slice(0, 2).map((s) => (
                        <button
                          key={s.key}
                          onClick={() => moveJob(job.id, s.key)}
                          className="rounded-lg px-1.5 py-0.5 text-[10px] transition-colors duration-200 bg-muted text-muted-foreground hover:bg-accent"
                        >
                          &rarr; {s.label}
                        </button>
                      ))}
                      <button
                        onClick={() => handlePrepare(job)}
                        className="rounded-lg px-1.5 py-0.5 text-[10px] transition-colors duration-200 bg-primary/10 text-primary hover:bg-primary/20"
                      >
                        AI Prep
                      </button>
                    </div>
                  </div>
                </Card>
              ))}
              {jobs.length === 0 && (
                <p className="text-[11px] text-center py-4 text-muted-foreground/70">No jobs</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// --- BY STATUS TAB ---

function ByStatusTab({
  jobs, loading, setSelectedJob, salary, handlePrepare,
}: {
  jobs: SavedJob[];
  loading: boolean;
  setSelectedJob: (j: SavedJob) => void;
  salary: (job: SavedJob) => string | null;
  handlePrepare: (job: SavedJob) => void;
}) {
  if (loading) return null;

  const grouped = STAGES.map((stage) => ({
    ...stage,
    jobs: jobs.filter((j) => j.status === stage.key),
  })).filter((g) => g.jobs.length > 0);

  if (grouped.length === 0) {
    return (
      <div className="text-center py-20">
        <p className="text-sm text-muted-foreground/70">No saved jobs yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {grouped.map((group) => (
        <div key={group.key}>
          <div className="flex items-center gap-2 mb-3">
            <div className={cn("h-2 w-2 rounded-full", group.color)} />
            <h3 className="text-[13px] font-semibold text-foreground">
              {group.label}
            </h3>
            <span className="data-mono text-[11px] text-muted-foreground/70">
              {group.jobs.length}
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {group.jobs.map((job) => (
              <Card
                key={job.id}
                onClick={() => setSelectedJob(job)}
                className="cursor-pointer p-4 group hover:bg-accent/50 transition-colors"
              >
                <div className="relative z-10">
                  <h4 className="text-[13px] font-semibold line-clamp-1 text-foreground">{job.title}</h4>
                  <p className="text-[11px] mt-0.5 text-muted-foreground/70">{job.company}</p>
                  <div className="flex items-center justify-between mt-2">
                    {salary(job) ? (
                      <span className="text-[11px] font-semibold data-mono text-primary">{salary(job)}</span>
                    ) : (
                      <span className="text-[10px] text-muted-foreground/70">{job.location}</span>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); handlePrepare(job); }}
                      className="rounded-lg px-2 py-1 text-[10px] font-medium opacity-0 group-hover:opacity-100 transition-all duration-200 bg-primary/10 text-primary hover:bg-primary/20"
                    >
                      AI Prep
                    </button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
