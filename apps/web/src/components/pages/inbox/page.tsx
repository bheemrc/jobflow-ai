"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ApprovalItem, JournalEntry, JournalEntryType } from "@/lib/types";
import Markdown from "@/components/markdown";

const AGENT_COLORS: Record<string, { bg: string; text: string }> = {
  "Resume Tailor": { bg: "rgba(239, 68, 68, 0.12)", text: "#EF4444" },
  "Forge": { bg: "rgba(239, 68, 68, 0.12)", text: "#EF4444" },
  "Recruiter Chat": { bg: "rgba(251, 191, 36, 0.12)", text: "#FBBF24" },
  "Catalyst": { bg: "rgba(251, 191, 36, 0.12)", text: "#FBBF24" },
  "LeetCode Coach": { bg: "rgba(34, 211, 238, 0.12)", text: "#22D3EE" },
  "Cipher": { bg: "rgba(34, 211, 238, 0.12)", text: "#22D3EE" },
  "Job Intake": { bg: "rgba(249, 115, 22, 0.12)", text: "#F97316" },
  "Pathfinder": { bg: "rgba(249, 115, 22, 0.12)", text: "#F97316" },
  "Interview Prep": { bg: "rgba(167, 139, 250, 0.12)", text: "#A78BFA" },
  "Strategist": { bg: "rgba(167, 139, 250, 0.12)", text: "#A78BFA" },
  "Sentinel": { bg: "rgba(148, 163, 184, 0.12)", text: "#94A3B8" },
  "Nexus": { bg: "rgba(88, 166, 255, 0.12)", text: "#58A6FF" },
};

const TYPE_LABELS: Record<string, string> = {
  resume_diff: "🔥 Forge Output",
  recruiter_reply: "✦ Catalyst Draft",
  solution_review: "◈ Cipher Review",
  general: "⬡ Agent Signal",
};

const STATUS_VARIANT: Record<string, "warning" | "success" | "destructive" | "info"> = {
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  applied: "info",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending Review",
  approved: "Approved",
  rejected: "Rejected",
  applied: "Applied",
};

const JOURNAL_TYPE_STYLES: Record<JournalEntryType, { border: string; label: string; variant: "info" | "success" | "secondary" | "warning" }> = {
  insight: { border: "#60A5FA", label: "Insight", variant: "info" },
  recommendation: { border: "#4ADE80", label: "Recommendation", variant: "success" },
  summary: { border: "#C084FC", label: "Summary", variant: "secondary" },
  note: { border: "#94A3B8", label: "Note", variant: "secondary" },
  action_item: { border: "#FBBF24", label: "Action Item", variant: "warning" },
};

const PRIORITY_STYLES: Record<string, { color: string }> = {
  high: { color: "#F87171" },
  medium: { color: "#FBBF24" },
  low: { color: "#94A3B8" },
};

type Tab = "approvals" | "journal";

export default function InboxPage() {
  const [activeTab, setActiveTab] = useState<Tab>("approvals");
  // Approvals state
  const [entries, setEntries] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<number, string>>({});
  const [localStatus, setLocalStatus] = useState<Record<number, string>>({});
  // Journal state
  const [journalEntries, setJournalEntries] = useState<JournalEntry[]>([]);
  const [journalLoading, setJournalLoading] = useState(true);
  const [journalFilter, setJournalFilter] = useState<JournalEntryType | "all">("all");
  const [expandedJournal, setExpandedJournal] = useState<number | null>(null);

  useEffect(() => {
    fetchEntries();
    fetchJournal();
  }, []);

  async function fetchEntries() {
    try {
      const res = await fetch("/api/ai/approvals");
      const data = await res.json();
      if (data?.approvals) setEntries(data.approvals);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function fetchJournal() {
    try {
      const res = await fetch("/api/ai/journal");
      const data = await res.json();
      if (data?.entries) setJournalEntries(data.entries);
    } catch {
      // ignore
    } finally {
      setJournalLoading(false);
    }
  }

  async function handleApprove(item: ApprovalItem) {
    setActionLoading((prev) => ({ ...prev, [item.id]: "approve" }));
    try {
      await fetch(`/api/ai/approvals/${item.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: "approved" }),
      });
      setLocalStatus((prev) => ({ ...prev, [item.id]: "approved" }));
    } catch {
      // ignore
    } finally {
      setActionLoading((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
    }
  }

  async function handleReject(item: ApprovalItem) {
    setActionLoading((prev) => ({ ...prev, [item.id]: "reject" }));
    try {
      await fetch(`/api/ai/approvals/${item.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: "rejected" }),
      });
      setLocalStatus((prev) => ({ ...prev, [item.id]: "rejected" }));
    } catch {
      // ignore
    } finally {
      setActionLoading((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
    }
  }

  function handleApplyChanges(item: ApprovalItem) {
    navigator.clipboard.writeText(item.content);
    setLocalStatus((prev) => ({ ...prev, [item.id]: "applied" }));
  }

  async function handleMarkRead(entry: JournalEntry) {
    try {
      await fetch(`/api/ai/journal/${entry.id}/read`, { method: "PATCH" });
      setJournalEntries((prev) =>
        prev.map((e) => (e.id === entry.id ? { ...e, is_read: true } : e))
      );
    } catch {}
  }

  async function handleTogglePin(entry: JournalEntry) {
    const newPinned = !entry.is_pinned;
    try {
      await fetch(`/api/ai/journal/${entry.id}/pin`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned: newPinned }),
      });
      setJournalEntries((prev) =>
        prev.map((e) => (e.id === entry.id ? { ...e, is_pinned: newPinned } : e))
      );
    } catch {}
  }

  async function handleDeleteJournal(entry: JournalEntry) {
    try {
      await fetch(`/api/ai/journal/${entry.id}`, { method: "DELETE" });
      setJournalEntries((prev) => prev.filter((e) => e.id !== entry.id));
    } catch {}
  }

  const unreadCount = journalEntries.filter((e) => !e.is_read).length;

  if (loading && journalLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <svg className="h-6 w-6 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="animate-fade-in-up">
        <div className="flex items-center gap-2.5">
          <span className="text-[20px]">◆</span>
          <h1 className="text-xl font-bold text-foreground">Sentinel Inbox</h1>
        </div>
        <p className="text-[12px] text-muted-foreground">
          Review approvals and intelligence from the Nexus collective
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl p-1 bg-muted">
        <button
          onClick={() => setActiveTab("approvals")}
          className={cn(
            "flex-1 rounded-lg px-4 py-2 text-[12px] font-semibold transition-all duration-200",
            activeTab === "approvals"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          ◆ Approvals
          {entries.filter((e) => (localStatus[e.id] || e.status) === "pending").length > 0 && (
            <Badge variant="warning" className="ml-1.5 text-[9px] px-1.5 py-0.5">
              {entries.filter((e) => (localStatus[e.id] || e.status) === "pending").length}
            </Badge>
          )}
        </button>
        <button
          onClick={() => setActiveTab("journal")}
          className={cn(
            "flex-1 rounded-lg px-4 py-2 text-[12px] font-semibold transition-all duration-200",
            activeTab === "journal"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          ◉ Intel Log
          {unreadCount > 0 && (
            <Badge variant="info" className="ml-1.5 text-[9px] px-1.5 py-0.5">
              {unreadCount}
            </Badge>
          )}
        </button>
      </div>

      {/* Approvals Tab */}
      {activeTab === "approvals" && (
        <>
          {entries.length === 0 ? (
            <Card className="p-8 text-center animate-fade-in">
              <div className="relative z-10">
                <svg
                  className="mx-auto h-12 w-12 text-muted-foreground opacity-40"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p className="mt-3 text-sm text-muted-foreground">No approvals pending</p>
                <p className="text-[12px] text-muted-foreground">
                  Agent outputs like resume diffs and recruiter drafts will appear here.
                </p>
              </div>
            </Card>
          ) : (
            <div className="space-y-3 stagger">
              {entries.map((item) => {
                const agentStyle = AGENT_COLORS[item.agent] || { bg: "hsl(var(--primary) / 0.1)", text: "hsl(var(--primary))" };
                const itemStatus = localStatus[item.id] || item.status;
                const statusVariant = STATUS_VARIANT[itemStatus] || "warning";
                const statusLabel = STATUS_LABELS[itemStatus] || itemStatus;
                const isLoading = !!actionLoading[item.id];
                const isDecided = itemStatus === "approved" || itemStatus === "rejected" || itemStatus === "applied";

                return (
                  <Card key={item.id} className="overflow-hidden">
                    <button
                      onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                      className="relative z-10 flex w-full items-center justify-between p-4 text-left transition-colors duration-200 hover:bg-muted/50"
                    >
                      <div className="flex items-center gap-3">
                        <Badge variant="secondary" style={{ background: agentStyle.bg, color: agentStyle.text }}>
                          {item.agent}
                        </Badge>
                        <div>
                          <p className="text-[13px] font-medium text-foreground">
                            {item.title}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {TYPE_LABELS[item.type] || item.type}
                            {item.created_at && ` · ${new Date(item.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={statusVariant} className="text-[10px]">
                          {statusLabel}
                        </Badge>
                        <svg
                          className={cn(
                            "h-4 w-4 transition-transform duration-200 text-muted-foreground",
                            expandedId === item.id && "rotate-180"
                          )}
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {expandedId === item.id && (
                      <div className="relative z-10 p-4 animate-fade-in border-t">
                        <div className="prose-sm max-w-none text-sm leading-relaxed text-muted-foreground">
                          <Markdown>{item.content}</Markdown>
                        </div>
                        <div className="mt-4 flex items-center gap-2 border-t pt-3">
                          {!isDecided ? (
                            <>
                              <Button
                                onClick={() => handleApprove(item)}
                                disabled={isLoading}
                                variant="outline"
                                size="sm"
                                className="text-[11px] font-semibold text-success border-success/30 bg-success/10 hover:bg-success/20"
                              >
                                {actionLoading[item.id] === "approve" ? "Approving..." : "Approve"}
                              </Button>
                              <Button
                                onClick={() => handleReject(item)}
                                disabled={isLoading}
                                variant="outline"
                                size="sm"
                                className="text-[11px] font-semibold text-destructive border-destructive/30 bg-destructive/10 hover:bg-destructive/20"
                              >
                                {actionLoading[item.id] === "reject" ? "Rejecting..." : "Reject"}
                              </Button>
                              {item.type === "resume_diff" && (
                                <Button
                                  onClick={() => handleApplyChanges(item)}
                                  disabled={isLoading}
                                  variant="outline"
                                  size="sm"
                                  className="text-[11px] font-semibold text-info border-info/30 bg-info/10 hover:bg-info/20"
                                >
                                  Apply Changes (Copy)
                                </Button>
                              )}
                            </>
                          ) : (
                            <Badge variant={statusVariant} className="text-[11px]">
                              {statusLabel}
                            </Badge>
                          )}
                          <Button
                            onClick={() => navigator.clipboard.writeText(item.content)}
                            variant="ghost"
                            size="sm"
                            className="text-[11px] ml-auto"
                          >
                            Copy
                          </Button>
                        </div>
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Journal Tab */}
      {activeTab === "journal" && (
        <>
          {/* Filter pills */}
          <div className="flex gap-2 flex-wrap">
            {(["all", "insight", "recommendation", "summary", "note", "action_item"] as const).map((type) => {
              const isActive = journalFilter === type;
              const typeInfo = type === "all"
                ? { label: "All", variant: "secondary" as const }
                : JOURNAL_TYPE_STYLES[type];
              const count = type === "all"
                ? journalEntries.length
                : journalEntries.filter((e) => e.entry_type === type).length;
              return (
                <Badge
                  key={type}
                  variant={isActive ? (type === "all" ? "secondary" : typeInfo.variant) : "secondary"}
                  className={cn(
                    "cursor-pointer transition-all duration-200 text-[11px]",
                    !isActive && "opacity-60 hover:opacity-100"
                  )}
                  onClick={() => setJournalFilter(type)}
                >
                  {typeInfo.label} ({count})
                </Badge>
              );
            })}
          </div>

          {journalEntries.length === 0 ? (
            <Card className="p-8 text-center animate-fade-in">
              <div className="relative z-10">
                <svg
                  className="mx-auto h-12 w-12 text-muted-foreground opacity-40"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
                  />
                </svg>
                <p className="mt-3 text-sm text-muted-foreground">No journal entries yet</p>
                <p className="text-[12px] text-muted-foreground">
                  Bots and agents will post insights, recommendations, and summaries here.
                </p>
              </div>
            </Card>
          ) : (
            <div className="space-y-2 stagger">
              {journalEntries
                .filter((e) => journalFilter === "all" || e.entry_type === journalFilter)
                .map((entry) => {
                  const typeStyle = JOURNAL_TYPE_STYLES[entry.entry_type] || JOURNAL_TYPE_STYLES.note;
                  const priorityStyle = PRIORITY_STYLES[entry.priority] || PRIORITY_STYLES.medium;
                  const isExpanded = expandedJournal === entry.id;
                  const tags = Array.isArray(entry.tags) ? entry.tags : [];

                  return (
                    <Card
                      key={entry.id}
                      className={cn("overflow-hidden", entry.is_read && "opacity-75")}
                      style={{ borderLeft: `3px solid ${typeStyle.border}` }}
                    >
                      <button
                        onClick={() => {
                          setExpandedJournal(isExpanded ? null : entry.id);
                          if (!entry.is_read) handleMarkRead(entry);
                        }}
                        className="relative z-10 flex w-full items-center justify-between p-4 text-left transition-colors duration-200 hover:bg-muted/50"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          {entry.is_pinned && (
                            <svg className="h-3.5 w-3.5 shrink-0 text-warning" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2z" />
                            </svg>
                          )}
                          <Badge variant={typeStyle.variant} className="shrink-0 text-[10px]">
                            {typeStyle.label}
                          </Badge>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <p
                                className={cn(
                                  "text-[13px] truncate text-foreground",
                                  entry.is_read ? "font-medium" : "font-semibold"
                                )}
                              >
                                {entry.title}
                              </p>
                              {!entry.is_read && (
                                <span className="h-2 w-2 rounded-full shrink-0 bg-info" />
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              {entry.agent && (
                                <span className="text-[10px] font-medium text-primary">
                                  {entry.agent}
                                </span>
                              )}
                              {entry.priority !== "medium" && (
                                <span className="text-[10px] font-medium capitalize" style={{ color: priorityStyle.color }}>
                                  {entry.priority}
                                </span>
                              )}
                              {tags.length > 0 && (
                                <span className="text-[10px] text-muted-foreground">
                                  {tags.slice(0, 3).join(", ")}
                                </span>
                              )}
                              <span className="text-[10px] text-muted-foreground">
                                {new Date(entry.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                              </span>
                            </div>
                          </div>
                        </div>
                        <svg
                          className={cn(
                            "h-4 w-4 shrink-0 transition-transform duration-200 text-muted-foreground",
                            isExpanded && "rotate-180"
                          )}
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>

                      {isExpanded && (
                        <div className="relative z-10 p-4 animate-fade-in border-t">
                          <div className="prose-sm max-w-none text-[12px] leading-relaxed text-muted-foreground">
                            <Markdown>{entry.content}</Markdown>
                          </div>

                          {tags.length > 0 && (
                            <div className="flex gap-1.5 flex-wrap mt-3">
                              {tags.map((tag) => (
                                <Badge key={tag} variant="secondary" className="text-[9px]">
                                  #{tag}
                                </Badge>
                              ))}
                            </div>
                          )}

                          <div className="mt-4 flex items-center gap-2 border-t pt-3">
                            <Button
                              onClick={() => handleTogglePin(entry)}
                              variant={entry.is_pinned ? "outline" : "ghost"}
                              size="sm"
                              className={cn(
                                "text-[11px] font-semibold",
                                entry.is_pinned && "text-warning border-warning/30 bg-warning/10"
                              )}
                            >
                              {entry.is_pinned ? "Unpin" : "Pin"}
                            </Button>
                            <Button
                              onClick={() => handleDeleteJournal(entry)}
                              variant="ghost"
                              size="sm"
                              className="text-[11px] font-semibold text-muted-foreground"
                            >
                              Delete
                            </Button>
                            <Button
                              onClick={() => navigator.clipboard.writeText(entry.content)}
                              variant="ghost"
                              size="sm"
                              className="text-[11px] font-medium ml-auto"
                            >
                              Copy
                            </Button>
                          </div>
                        </div>
                      )}
                    </Card>
                  );
                })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
