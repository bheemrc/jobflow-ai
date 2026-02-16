"use client";

import { JobResult } from "@/lib/types";
import { getSimilarRoles } from "@/lib/role-suggestions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MapPin, Bookmark, Check, ExternalLink, X } from "lucide-react";
import Markdown from "./markdown";

/** Clean raw description text for better markdown rendering. */
function cleanDescription(raw: string): string {
  return raw
    .replace(/\\([*\-#_~`|])/g, "$1")
    .replace(/\r\n/g, "\n");
}

/** Format salary range. */
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

/** Convert date string to a friendly format. */
function formatDate(dateStr: string | null): string | null {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "Posted today";
    if (diffDays === 1) return "Posted yesterday";
    if (diffDays < 7) return `Posted ${diffDays} days ago`;
    if (diffDays < 30) return `Posted ${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) > 1 ? "s" : ""} ago`;
    return `Posted ${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
  } catch {
    return dateStr;
  }
}

/** Deterministic gradient from company name. */
function avatarGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `linear-gradient(135deg, hsl(${hue}, 45%, 35%), hsl(${(hue + 40) % 360}, 50%, 25%))`;
}

function companyInitial(name: string): string {
  return (name || "?").charAt(0).toUpperCase();
}

interface SearchJobDetailProps {
  job: JobResult;
  onClose: () => void;
  onSave: (job: JobResult) => void;
  isSaved: boolean;
  onSearchRole: (term: string) => void;
}

export default function SearchJobDetail({
  job,
  onClose,
  onSave,
  isSaved,
  onSearchRole,
}: SearchJobDetailProps) {
  const salary = formatSalary(job.min_amount, job.max_amount);
  const posted = formatDate(job.date_posted);
  const similarRoles = getSimilarRoles(job);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="px-6 py-5 shrink-0 border-b">
        <div className="flex items-start gap-4">
          {/* Company logo */}
          <div className="shrink-0">
            {job.employer_logo ? (
              <div className="h-12 w-12 rounded-xl overflow-hidden flex items-center justify-center bg-muted border">
                <img
                  src={job.employer_logo}
                  alt=""
                  className="h-full w-full object-contain p-1.5"
                  onError={(e) => {
                    const target = e.currentTarget;
                    const parent = target.parentElement;
                    if (parent) {
                      parent.style.background = avatarGradient(job.company);
                      parent.style.border = "none";
                      parent.innerHTML = `<span style="color: rgba(255,255,255,0.85); font-size: 18px; font-weight: 700;">${companyInitial(job.company)}</span>`;
                    }
                  }}
                />
              </div>
            ) : (
              <div
                className="h-12 w-12 rounded-xl flex items-center justify-center"
                style={{ background: avatarGradient(job.company) }}
              >
                <span className="text-[18px] font-bold text-white/85">
                  {companyInitial(job.company)}
                </span>
              </div>
            )}
          </div>

          {/* Title + Company */}
          <div className="min-w-0 flex-1">
            <h2 className="text-[17px] font-bold leading-snug line-clamp-2 text-foreground tracking-tight">
              {job.title}
            </h2>
            <p className="mt-1 text-[13px] font-medium text-muted-foreground">
              {job.company}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1.5 shrink-0">
            <Button
              onClick={(e) => { e.stopPropagation(); onSave(job); }}
              disabled={isSaved}
              variant={isSaved ? "ghost" : "default"}
              size="sm"
              className={cn(
                "text-[12px] font-semibold gap-1.5",
                isSaved && "bg-success/10 text-success hover:bg-success/10 hover:text-success"
              )}
            >
              {isSaved ? (
                <>
                  <Check className="h-3.5 w-3.5" />
                  Saved
                </>
              ) : (
                <>
                  <Bookmark className="h-3.5 w-3.5" />
                  Save
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              asChild
              className="text-[12px] font-semibold gap-1.5 hover:border-primary hover:text-primary"
            >
              <a
                href={job.job_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Apply
                <ExternalLink className="h-3.5 w-3.5" />
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

        {/* Meta badges row */}
        <div className="mt-3 ml-16 flex flex-wrap items-center gap-2.5">
          {/* Location */}
          <span className="inline-flex items-center gap-1 text-[12px] text-muted-foreground">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            {job.location}
          </span>

          {job.is_remote && (
            <Badge variant="success" className="text-[11px]">
              Remote
            </Badge>
          )}

          {salary && (
            <Badge variant="info" className="text-[11px] font-bold font-mono">
              {salary}
            </Badge>
          )}

          {job.job_type && (
            <Badge variant="secondary" className="text-[11px]">
              {job.job_type}
            </Badge>
          )}

          {posted && (
            <span className="text-[11px] font-mono text-muted-foreground">
              {posted}
            </span>
          )}

          {job.site && (
            <>
              <span className="text-muted-foreground/30">&middot;</span>
              <span className="uppercase tracking-wider font-mono text-muted-foreground text-[10px]">
                via {job.site}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Body -- scrollable */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {job.description && (
          <div className="text-[13px] leading-[1.75] text-muted-foreground">
            <Markdown>{cleanDescription(job.description)}</Markdown>
          </div>
        )}

        {!job.description && (
          <div className="flex flex-col items-center justify-center py-12">
            <p className="text-[13px] text-muted-foreground">
              No description available.
            </p>
            <a
              href={job.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 text-[13px] font-medium text-primary hover:text-primary/80 transition-colors duration-200"
            >
              View on {job.site || "source"} &rarr;
            </a>
          </div>
        )}

        {/* Similar roles */}
        {similarRoles.length > 0 && (
          <div className="mt-6 rounded-xl p-4 bg-muted border">
            <p className="text-[10px] font-bold uppercase tracking-wider mb-2.5 text-muted-foreground">
              Find Similar Roles
            </p>
            <div className="flex flex-wrap gap-1.5">
              {similarRoles.map((role) => (
                <Button
                  key={role}
                  variant="outline"
                  size="sm"
                  onClick={() => onSearchRole(role)}
                  className="rounded-full text-[11px] font-medium hover:border-primary hover:text-primary hover:bg-primary/10 h-auto py-1.5 px-3"
                >
                  {role}
                </Button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
