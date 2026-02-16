"use client";

import { JobResult } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MapPin, Bookmark, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import MatchScoreBadge from "./match-score-badge";

interface JobCardProps {
  job: JobResult;
  onSave: (job: JobResult) => void;
  isSaved: boolean;
  matchScore?: number;
  onClick?: () => void;
}

/** Strip markdown syntax and escaped chars for clean plain-text preview. */
function stripMarkdown(raw: string): string {
  return raw
    .replace(/\\([*\-#_~`|])/g, "$1")
    .replace(/[*_~`#>]/g, "")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\n{2,}/g, " \u00b7 ")
    .replace(/\n/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/** Format salary range compactly. */
function formatSalary(min: number | null, max: number | null): string | null {
  const hasMin = min != null && min > 0;
  const hasMax = max != null && max > 0;
  if (!hasMin && !hasMax) return null;

  const fmt = (n: number) => {
    if (n >= 1000) return `$${(n / 1000).toFixed(0)}k`;
    return `$${n}`;
  };

  if (hasMin && hasMax) return `${fmt(min!)} \u2013 ${fmt(max!)}`;
  if (hasMin) return `${fmt(min!)}+`;
  return `up to ${fmt(max!)}`;
}

/** Convert date string to relative time. */
function relativeDate(dateStr: string | null): string | null {
  if (!dateStr) return null;
  try {
    const posted = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - posted.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return "upcoming";
    if (diffDays === 0) return "today";
    if (diffDays === 1) return "1d ago";
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return `${Math.floor(diffDays / 30)}mo ago`;
  } catch {
    return dateStr;
  }
}

/** Get company initial for fallback avatar. */
function companyInitial(name: string): string {
  return (name || "?").charAt(0).toUpperCase();
}

/** Deterministic color from company name for fallback avatar. */
function avatarGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `linear-gradient(135deg, hsl(${hue}, 45%, 35%), hsl(${(hue + 40) % 360}, 50%, 25%))`;
}

export default function JobCard({ job, onSave, isSaved, matchScore, onClick }: JobCardProps) {
  const salary = formatSalary(job.min_amount, job.max_amount);
  const posted = relativeDate(job.date_posted);
  const description = job.description ? stripMarkdown(job.description) : null;

  return (
    <Card
      className={cn(
        "group relative overflow-hidden transition-all duration-200 hover:border-border hover:shadow-md hover:-translate-y-0.5",
        onClick && "cursor-pointer"
      )}
      onClick={onClick}
    >
      <div className="p-4">
        {/* Top row: Logo + Title + Save */}
        <div className="flex gap-3">
          {/* Company logo / fallback */}
          <div className="shrink-0 mt-0.5">
            {job.employer_logo ? (
              <div className="h-10 w-10 rounded-lg overflow-hidden flex items-center justify-center bg-muted border">
                <img
                  src={job.employer_logo}
                  alt=""
                  className="h-full w-full object-contain p-1"
                  onError={(e) => {
                    const target = e.currentTarget;
                    const parent = target.parentElement;
                    if (parent) {
                      parent.style.background = avatarGradient(job.company);
                      parent.style.border = "none";
                      parent.innerHTML = `<span style="color: rgba(255,255,255,0.85); font-size: 15px; font-weight: 700; letter-spacing: -0.02em;">${companyInitial(job.company)}</span>`;
                    }
                  }}
                />
              </div>
            ) : (
              <div
                className="h-10 w-10 rounded-lg flex items-center justify-center"
                style={{ background: avatarGradient(job.company) }}
              >
                <span className="text-[15px] font-bold tracking-tight text-white/85">
                  {companyInitial(job.company)}
                </span>
              </div>
            )}
          </div>

          {/* Title + Company */}
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold leading-snug line-clamp-2 text-foreground">
              {job.title}
            </p>
            <p className="mt-0.5 text-[12px] font-medium text-muted-foreground">
              {job.company}
            </p>
          </div>

          {/* Save button */}
          <Button
            variant={isSaved ? "ghost" : "outline"}
            size="icon"
            onClick={(e) => { e.stopPropagation(); onSave(job); }}
            disabled={isSaved}
            className={cn(
              "shrink-0 h-8 w-8 rounded-lg",
              isSaved
                ? "bg-success/10 text-success border-transparent hover:bg-success/10 hover:text-success"
                : "text-muted-foreground hover:bg-primary/10 hover:text-primary hover:border-primary"
            )}
            title={isSaved ? "Saved" : "Save job"}
          >
            {isSaved ? (
              <Check className="h-4 w-4" />
            ) : (
              <Bookmark className="h-4 w-4" />
            )}
          </Button>
        </div>

        {matchScore !== undefined && (
          <div className="mt-2.5 ml-[52px]">
            <MatchScoreBadge score={matchScore} />
          </div>
        )}

        {/* Meta row: location, salary, badges */}
        <div className="mt-3 ml-[52px] flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          {/* Location */}
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" />
            {job.location}
          </span>

          {/* Salary */}
          {salary && (
            <span className="inline-flex items-center text-[11px] font-bold font-mono tracking-tight text-primary">
              {salary}
            </span>
          )}

          {/* Remote badge */}
          {job.is_remote && (
            <Badge variant="success" className="text-[10px] py-0">
              Remote
            </Badge>
          )}

          {/* Job type */}
          {job.job_type && (
            <Badge variant="secondary" className="text-[10px] py-0">
              {job.job_type}
            </Badge>
          )}

          {/* Spacer + date + source aligned right */}
          <span className="ml-auto inline-flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
            {posted && <span>{posted}</span>}
            {job.site && (
              <>
                <span className="opacity-30">&middot;</span>
                <span className="uppercase tracking-wider text-[9px]">{job.site}</span>
              </>
            )}
          </span>
        </div>

        {/* Description preview */}
        {description && (
          <p className="mt-2.5 ml-[52px] text-[11.5px] leading-[1.6] line-clamp-2 text-muted-foreground">
            {description}
          </p>
        )}
      </div>
    </Card>
  );
}
