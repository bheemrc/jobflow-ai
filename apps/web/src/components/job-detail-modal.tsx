"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SavedJob, JobStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  ExternalLink,
  X,
  Sparkles,
  FileSearch,
  FileText,
  GraduationCap,
  Loader2,
  Copy,
  Check,
} from "lucide-react";
import StatusBadge from "./status-badge";
import Markdown from "./markdown";

const STATUSES: JobStatus[] = ["saved", "applied", "interview", "offer", "rejected"];
type Tab = "overview" | "ai-prep" | "cover-letter";

interface JobDetailModalProps {
  job: SavedJob;
  onClose: () => void;
  onUpdate: (job: SavedJob) => void;
}

export default function JobDetailModal({ job, onClose, onUpdate }: JobDetailModalProps) {
  const router = useRouter();
  const [notes, setNotes] = useState(job.notes);
  const [status, setStatus] = useState<JobStatus>(job.status);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const [analysis, setAnalysis] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [coverLetter, setCoverLetter] = useState<string | null>(null);
  const [coverLetterLoading, setCoverLetterLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const res = await fetch(`/api/jobs/${job.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes, status }),
      });
      if (res.ok) {
        const updated = await res.json();
        onUpdate(updated);
        onClose();
      }
    } finally {
      setSaving(false);
    }
  }

  function handleFullPrepare() {
    const params = new URLSearchParams();
    params.set("company", job.company);
    params.set("role", job.title);
    params.set("job_id", String(job.id));
    params.set("source", "saved_job");
    router.push(`/ai?${params.toString()}`);
  }

  async function handleAnalyze() {
    setAnalysisLoading(true);
    try {
      const res = await fetch("/api/ai/coach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `Analyze this job posting and give me: 1) Match score against my resume, 2) Key skills required vs what I have, 3) Salary research, 4) Application strategy.\n\nTitle: ${job.title}\nCompany: ${job.company}\nLocation: ${job.location}\n\n${job.description || "No description available."}`,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAnalysis(data.response);
      } else {
        setAnalysis("Failed to get AI analysis. Make sure the AI service is running.");
      }
    } catch {
      setAnalysis("Failed to connect to AI service.");
    } finally {
      setAnalysisLoading(false);
    }
  }

  async function handleGenerateCoverLetter() {
    setCoverLetterLoading(true);
    try {
      const resumesRes = await fetch("/api/ai/resumes");
      const resumesData = await resumesRes.json();
      const resumeId = resumesData.resumes?.[0];

      if (!resumeId) {
        setCoverLetter("Please upload your resume first using the AI Coach page or the My Jobs page.");
        setCoverLetterLoading(false);
        return;
      }

      const res = await fetch("/api/ai/coach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `Write a cover letter for this job application. Use my resume to highlight relevant experience. Make it specific to the company and role.\n\nTitle: ${job.title}\nCompany: ${job.company}\n\n${job.description || "No description available."}`,
          context: { resume_id: resumeId },
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setCoverLetter(data.response);
      } else {
        setCoverLetter("Failed to generate cover letter.");
      }
    } catch {
      setCoverLetter("Failed to connect to AI service.");
    } finally {
      setCoverLetterLoading(false);
    }
  }

  function handleCopy() {
    if (coverLetter) {
      navigator.clipboard.writeText(coverLetter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className="w-[440px] shrink-0 flex flex-col h-full overflow-hidden animate-slide-in-right bg-card border-l">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 px-5 py-4 border-b">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold line-clamp-2 text-foreground">{job.title}</h2>
          <p className="mt-0.5 text-[12px] text-muted-foreground">{job.company} &middot; {job.location}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <StatusBadge status={job.status} />
            {job.is_remote && (
              <Badge variant="success">Remote</Badge>
            )}
            {(job.min_amount || job.max_amount) && (
              <span className="text-[11px] font-semibold font-mono text-primary">
                {[job.min_amount && `$${(job.min_amount / 1000).toFixed(0)}k`, job.max_amount && `$${(job.max_amount / 1000).toFixed(0)}k`]
                  .filter(Boolean)
                  .join(" - ")}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
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
            onClick={onClose}
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-5 py-2.5 border-b">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as Tab)}>
          <TabsList className="h-8">
            <TabsTrigger value="overview" className="text-[11px] px-3 py-1.5">Overview</TabsTrigger>
            <TabsTrigger value="ai-prep" className="text-[11px] px-3 py-1.5">AI Prep</TabsTrigger>
            <TabsTrigger value="cover-letter" className="text-[11px] px-3 py-1.5">Cover Letter</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {activeTab === "overview" && (
          <div className="space-y-4">
            {/* Quick AI Actions */}
            <div className="rounded-xl p-4 bg-primary/5 border border-primary/20">
              <p className="text-[11px] font-semibold mb-3 text-primary">AI Actions</p>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleFullPrepare}
                  className="justify-start text-[11px] h-auto py-2 px-3"
                >
                  <Sparkles className="h-3.5 w-3.5 mb-1" />
                  Full Prep
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setActiveTab("ai-prep")}
                  className="justify-start text-[11px] h-auto py-2 px-3"
                >
                  <FileSearch className="h-3.5 w-3.5 mb-1" />
                  Quick Analysis
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setActiveTab("cover-letter")}
                  className="justify-start text-[11px] h-auto py-2 px-3"
                >
                  <FileText className="h-3.5 w-3.5 mb-1" />
                  Cover Letter
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  asChild
                  className="justify-start text-[11px] h-auto py-2 px-3"
                >
                  <a href={`/ai?company=${encodeURIComponent(job.company)}&role=${encodeURIComponent(job.title)}&source=interview_prep`}>
                    <GraduationCap className="h-3.5 w-3.5 mb-1" />
                    Interview Prep
                  </a>
                </Button>
              </div>
            </div>

            {job.description && (
              <div>
                <label className="mb-1.5 block text-[11px] font-semibold text-muted-foreground">Job Description</label>
                <div className="max-h-52 overflow-y-auto rounded-xl p-3 text-[12px] leading-relaxed whitespace-pre-wrap bg-muted border text-muted-foreground">
                  {job.description}
                </div>
              </div>
            )}

            <div>
              <label className="mb-1 block text-[11px] font-semibold text-muted-foreground">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as JobStatus)}
                className="flex h-10 w-full rounded-xl border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring capitalize"
              >
                {STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-[11px] font-semibold text-muted-foreground">Notes</label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={4}
                className="rounded-xl text-sm resize-none"
                placeholder="Add your notes here..."
              />
            </div>
          </div>
        )}

        {activeTab === "ai-prep" && (
          <div>
            {!analysis && !analysisLoading && (
              <div className="flex flex-col items-center py-8">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl mb-3 bg-primary/10">
                  <Sparkles className="h-7 w-7 text-primary" />
                </div>
                <p className="mb-1 text-sm font-medium text-foreground">AI Job Analysis</p>
                <p className="mb-4 text-[12px] text-center max-w-xs text-muted-foreground">
                  Get a quick match score, skill gap analysis, and application strategy.
                </p>
                <div className="flex gap-2">
                  <Button onClick={handleAnalyze} size="sm" className="text-[12px]">
                    Quick Analysis
                  </Button>
                  <Button
                    onClick={handleFullPrepare}
                    variant="outline"
                    size="sm"
                    className="text-[12px] border-primary/20 text-primary hover:bg-primary/10"
                  >
                    Full AI Prep
                  </Button>
                </div>
              </div>
            )}
            {analysisLoading && (
              <div className="flex flex-col items-center py-10">
                <Loader2 className="h-5 w-5 animate-spin mb-2 text-primary" />
                <p className="text-[12px] text-muted-foreground">Analyzing job posting...</p>
              </div>
            )}
            {analysis && (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] font-semibold text-muted-foreground">Analysis Results</span>
                  <Button
                    onClick={handleFullPrepare}
                    variant="ghost"
                    size="sm"
                    className="text-[10px] text-primary h-auto py-1 px-3"
                  >
                    Full Prep in AI Coach
                  </Button>
                </div>
                <div className="rounded-xl p-4 text-[12px] leading-relaxed bg-muted border text-muted-foreground">
                  <Markdown>{analysis}</Markdown>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "cover-letter" && (
          <div>
            {!coverLetter && !coverLetterLoading && (
              <div className="flex flex-col items-center py-8">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl mb-3 bg-purple-500/10">
                  <FileText className="h-7 w-7 text-purple-500" />
                </div>
                <p className="mb-1 text-sm font-medium text-foreground">Cover Letter</p>
                <p className="mb-4 text-[12px] text-center max-w-xs text-muted-foreground">
                  Generate a tailored cover letter using your resume and this job posting.
                </p>
                <Button onClick={handleGenerateCoverLetter} size="sm" className="text-[12px]">
                  Generate Cover Letter
                </Button>
              </div>
            )}
            {coverLetterLoading && (
              <div className="flex flex-col items-center py-10">
                <Loader2 className="h-5 w-5 animate-spin mb-2 text-primary" />
                <p className="text-[12px] text-muted-foreground">Generating cover letter...</p>
              </div>
            )}
            {coverLetter && (
              <div className="space-y-2">
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopy}
                    className={cn(
                      "text-[10px] h-auto py-1 px-2.5",
                      copied && "text-success"
                    )}
                  >
                    {copied ? (
                      <>
                        <Check className="h-3 w-3 mr-1" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" />
                        Copy
                      </>
                    )}
                  </Button>
                </div>
                <Textarea
                  value={coverLetter}
                  onChange={(e) => setCoverLetter(e.target.value)}
                  rows={14}
                  className="rounded-xl text-[12px] leading-relaxed resize-none"
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      {activeTab === "overview" && (
        <div className="flex gap-2 px-5 py-3 border-t bg-muted">
          <Button variant="ghost" onClick={onClose} className="flex-1 text-[12px]">
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 text-[12px]"
          >
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      )}
    </div>
  );
}
