"use client";

import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import Link from "next/link";
import type { PipelineJob, ActivityLogEntry } from "@/lib/types";
import OnboardingWizard from "@/components/onboarding-wizard";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, BookOpen, Sparkles, ChevronRight, Plus, AlertTriangle } from "lucide-react";

/* ── constants ── */

const STAGES = ["saved", "applied", "interview", "offer"] as const;

const STAGE_META: Record<string, { label: string; color: string; twText: string; twBg: string }> = {
  saved:     { label: "Saved",     color: "#9CA3AF", twText: "text-gray-400",   twBg: "bg-gray-400" },
  applied:   { label: "Applied",   color: "#60A5FA", twText: "text-blue-400",   twBg: "bg-blue-400" },
  interview: { label: "Interview", color: "#4ADE80", twText: "text-green-400",  twBg: "bg-green-400" },
  offer:     { label: "Offer",     color: "#FBBF24", twText: "text-yellow-400", twBg: "bg-yellow-400" },
};

const STAGE_BADGE_VARIANT: Record<string, "secondary" | "info" | "success" | "warning"> = {
  saved: "secondary",
  applied: "info",
  interview: "success",
  offer: "warning",
};

const ACTIONS = [
  {
    href: "/search",
    title: "Find Jobs",
    desc: "Search across job boards. Get AI-powered matches for your profile.",
    icon: Search,
    iconColor: "text-blue-400",
    iconBg: "bg-blue-500/10",
    hoverBorder: "hover:border-blue-500/30",
  },
  {
    href: "/prep",
    title: "Prepare",
    desc: "Interview materials, coding practice, and study guides for your target roles.",
    icon: BookOpen,
    iconColor: "text-green-400",
    iconBg: "bg-green-500/10",
    hoverBorder: "hover:border-green-500/30",
  },
  {
    href: "/ai",
    title: "AI Coach",
    desc: "Chat with your career coach. Resume reviews, strategy, and personalized guidance.",
    icon: Sparkles,
    iconColor: "text-violet-400",
    iconBg: "bg-violet-500/10",
    hoverBorder: "hover:border-violet-500/30",
  },
] as const;

/* ── helpers ── */

function fetchQ(url: string, ms = 4000) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  return fetch(url, { signal: c.signal }).finally(() => clearTimeout(t));
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

/* ── component ── */

export default function DashboardPage() {
  const onboardingComplete = useAppStore((s) => s.onboardingComplete);
  const agents = useAppStore((s) => s.agents);
  const setAgents = useAppStore((s) => s.setAgents);
  const approvals = useAppStore((s) => s.approvals);
  const setApprovals = useAppStore((s) => s.setApprovals);
  const pipelineJobs = useAppStore((s) => s.pipelineJobs);
  const setPipelineJobs = useAppStore((s) => s.setPipelineJobs);
  const activityLog = useAppStore((s) => s.activityLog);
  const setActivityLog = useAppStore((s) => s.setActivityLog);

  const [loaded, setLoaded] = useState(false);

  useEffect(() => { useAppStore.persist.rehydrate(); }, []);

  useEffect(() => {
    let done = 0;
    const bump = () => { done++; if (done >= 4) setLoaded(true); };

    fetchQ("/api/ai/agents/status")
      .then((r) => r.json()).then((d) => { if (d?.agents) setAgents(d.agents); }).catch(() => {}).finally(bump);
    fetchQ("/api/ai/approvals")
      .then((r) => r.json()).then((d) => { if (d?.approvals) setApprovals(d.approvals); }).catch(() => {}).finally(bump);
    fetchQ("/api/ai/jobs/pipeline")
      .then((r) => r.json()).then((d) => { if (d && typeof d === "object") setPipelineJobs(d); }).catch(() => {}).finally(bump);
    fetchQ("/api/ai/activity")
      .then((r) => r.json()).then((d) => { if (d?.activity) setActivityLog(d.activity); }).catch(() => {}).finally(bump);
  }, [setAgents, setApprovals, setPipelineJobs, setActivityLog]);

  // Show onboarding wizard if not completed
  if (!onboardingComplete) return <OnboardingWizard />;

  /* derived data */
  const counts = STAGES.reduce((a, s) => { a[s] = (pipelineJobs[s] || []).length; return a; }, {} as Record<string, number>);
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  const activeApps = Object.values(pipelineJobs)
    .flat()
    .filter((j) => j.status !== "rejected")
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 3);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });

  return (
    <div className="p-6 space-y-6 max-w-[1200px] mx-auto">

      {/* ── Header ── */}
      <div className="animate-fade-in-up flex items-end justify-between">
        <div>
          <h1 className="text-[22px] font-bold mb-1 text-foreground">
            Welcome back
          </h1>
          <p className="text-[13px] text-muted-foreground/70">
            Here&apos;s your job search at a glance
          </p>
        </div>
        <span className="data-mono text-[11px] pb-0.5 text-muted-foreground/70">
          {today}
        </span>
      </div>

      {/* ── Hero Cards — 3 clear value props ── */}
      <div className="grid grid-cols-3 gap-3 stagger">
        {ACTIONS.map((a) => {
          const Icon = a.icon;
          return (
            <Link key={a.href} href={a.href}>
              <Card className={cn(
                "p-5 group cursor-pointer transition-colors",
                a.hoverBorder
              )}>
                <div className={cn(
                  "w-10 h-10 rounded-xl flex items-center justify-center mb-3 transition-transform group-hover:scale-110",
                  a.iconBg
                )}>
                  <Icon className={cn("w-5 h-5", a.iconColor)} />
                </div>
                <p className="text-[14px] font-semibold mb-1 text-foreground">{a.title}</p>
                <p className="text-[11px] leading-relaxed text-muted-foreground/70">{a.desc}</p>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-3 gap-5">

        {/* Left — 2 cols */}
        <div className="col-span-2 space-y-5 stagger">

          {/* Pipeline */}
          <Link href="/saved" className="block">
            <Card className="p-5 transition-colors hover:bg-accent/50">
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] font-bold tracking-[0.08em] uppercase text-muted-foreground">Pipeline Overview</span>
                <span className="data-mono text-[11px] text-muted-foreground/70">
                  {total} job{total !== 1 ? "s" : ""}
                </span>
              </div>

              <div className="flex gap-3">
                {STAGES.map((stage, i) => {
                  const meta = STAGE_META[stage];
                  const pct = total > 0 ? Math.max((counts[stage] / total) * 100, 6) : 0;
                  return (
                    <div key={stage} className="flex items-center gap-3 flex-1">
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[11px] font-medium text-muted-foreground/70">
                            {meta.label}
                          </span>
                          <span className={cn("data-mono text-[14px] font-bold", meta.twText)}>
                            {counts[stage]}
                          </span>
                        </div>
                        <div className="h-[6px] rounded-full bg-muted">
                          <div
                            className={cn("h-full rounded-full transition-all duration-500", meta.twBg)}
                            style={{
                              width: counts[stage] > 0 ? `${pct}%` : "0%",
                              opacity: counts[stage] > 0 ? 1 : 0,
                            }}
                          />
                        </div>
                      </div>
                      {i < STAGES.length - 1 && (
                        <ChevronRight className="w-3 h-3 shrink-0 mt-4 text-muted-foreground/40" />
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          </Link>

          {/* Active Applications */}
          <Card className="p-5">
            <span className="text-[10px] font-bold tracking-[0.08em] uppercase text-muted-foreground">Active Applications</span>

            {activeApps.length === 0 ? (
              <Link
                href="/search"
                className="mt-4 flex items-center gap-4 p-4 rounded-xl transition-all hover:scale-[1.01] bg-card border border-dashed border-border"
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-blue-500/10">
                  <Plus className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-[13px] font-semibold text-foreground">
                    Start Searching
                  </p>
                  <p className="text-[11px] text-muted-foreground/70">
                    Search job boards and save opportunities to your pipeline
                  </p>
                </div>
              </Link>
            ) : (
              <div className="mt-3 space-y-2">
                {activeApps.map((job) => {
                  const meta = STAGE_META[job.status] || STAGE_META.saved;
                  const badgeVariant = STAGE_BADGE_VARIANT[job.status] || "secondary";
                  return (
                    <div
                      key={job.id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-muted/50"
                    >
                      <div
                        className={cn("w-1.5 h-8 rounded-full shrink-0", meta.twBg)}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium truncate text-foreground">
                          {job.title}
                        </p>
                        <p className="text-[11px] truncate text-muted-foreground/70">
                          {job.company}{job.location ? ` · ${job.location}` : ""}
                        </p>
                      </div>
                      <Badge variant={badgeVariant} className="shrink-0">
                        {meta.label}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        {/* Right — 1 col */}
        <div className="space-y-5 stagger">

          {/* Quick Stats */}
          <Card className="p-5">
            <div className="flex items-center justify-between mb-4">
              <span className="text-[10px] font-bold tracking-[0.08em] uppercase text-muted-foreground">Quick Stats</span>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-success shadow-[0_0_6px_hsl(var(--success))]" />
                <span className="text-[10px] font-medium text-success">Online</span>
              </div>
            </div>

            {/* Summary chips */}
            <div className="flex flex-wrap gap-2 mb-4">
              <Badge variant="info">
                {total} job{total !== 1 ? "s" : ""} tracked
              </Badge>
              <Badge variant="secondary">
                {agents.length} agent{agents.length !== 1 ? "s" : ""}
              </Badge>
              {approvals.length > 0 && (
                <Badge variant="warning">
                  {approvals.length} pending
                </Badge>
              )}
            </div>

            {/* Approval badge */}
            {approvals.length > 0 && (
              <Link
                href="/ai"
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl mb-4 transition-colors bg-warning/10 border border-warning/15 hover:bg-warning/15"
              >
                <AlertTriangle className="w-4 h-4 shrink-0 text-warning" />
                <span className="text-[12px] font-semibold text-warning">
                  {approvals.length} approval{approvals.length !== 1 ? "s" : ""} waiting
                </span>
              </Link>
            )}

            {/* Recent Activity */}
            {activityLog.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 text-muted-foreground/70">
                  Recent Activity
                </p>
                <div className="space-y-1.5">
                  {activityLog.slice(0, 3).map((entry) => (
                    <div key={entry.id} className="flex items-start gap-2.5 px-1">
                      <span className="w-[5px] h-[5px] rounded-full mt-[7px] shrink-0 bg-border" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[12px] leading-snug truncate text-muted-foreground">
                          {entry.action}
                        </p>
                        <p className="data-mono text-[10px] text-muted-foreground/70">
                          {entry.agent}{entry.created_at ? ` · ${timeAgo(entry.created_at)}` : ""}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty state when nothing loaded */}
            {!loaded && agents.length === 0 && (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-2.5 px-2.5 py-2">
                    <Skeleton className="w-[7px] h-[7px] rounded-full" />
                    <Skeleton className="h-3 flex-1" />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
