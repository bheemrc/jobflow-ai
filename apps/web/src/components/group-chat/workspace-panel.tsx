"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface WorkspaceTask {
  id: number;
  task_key: string;
  title: string;
  description: string;
  status: string;
  assigned_to: string | null;
  created_by: string;
  result: string | null;
}

interface WorkspaceFinding {
  id: number;
  finding_key: string;
  content: string;
  source_agent: string;
  category: string;
  confidence: number;
  tags?: string[];
}

interface WorkspaceDecision {
  id: number;
  decision_key: string;
  title: string;
  description: string;
  proposed_by: string;
  status: string;
  votes_for: string[];
  votes_against: string[];
  rationale?: string;
}

interface WorkspaceData {
  group_chat_id: number;
  tasks: WorkspaceTask[];
  findings: WorkspaceFinding[];
  decisions: WorkspaceDecision[];
  summary: {
    total_tasks: number;
    completed_tasks: number;
    total_findings: number;
    total_decisions: number;
    approved_decisions: number;
  };
}

interface WorkspacePanelProps {
  chatId: number;
  isActive: boolean;
}

// Icons
function LightbulbIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18h6M10 22h4M12 2v1M4.22 4.22l.71.71M1 12h1M4.22 19.78l.71-.71M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z"/>
    </svg>
  );
}

function CheckCircleIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
      <polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
  );
}

function ScaleIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/>
      <path d="M2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1z"/>
      <path d="M7 21h10M12 3v18M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
    </svg>
  );
}

function CopyIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  );
}

function CheckIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  );
}

function ChevronDownIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  );
}

function ChevronUpIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="18 15 12 9 6 15"/>
    </svg>
  );
}

// Copy button with feedback
function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button
      onClick={handleCopy}
      variant="ghost"
      size="sm"
      className={cn(
        "h-6 px-2 text-[10px] font-medium shrink-0",
        copied ? "text-success bg-success/10" : "text-muted-foreground"
      )}
    >
      {copied ? <CheckIcon className="w-3 h-3" /> : <CopyIcon className="w-3 h-3" />}
      {copied ? "Copied!" : label}
    </Button>
  );
}

// Confidence bar visualization
function ConfidenceBar({ confidence }: { confidence: number }) {
  const percentage = Math.round(confidence * 100);
  const colorClass = percentage >= 80 ? "bg-success" : percentage >= 60 ? "bg-warning" : "bg-destructive";
  const textClass = percentage >= 80 ? "text-success" : percentage >= 60 ? "text-warning" : "text-destructive";

  return (
    <div className="flex items-center gap-1.5 shrink-0">
      <div className="w-14 h-1.5 rounded-full overflow-hidden bg-muted">
        <div
          className={cn("h-full rounded-full transition-all", colorClass)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className={cn("text-[10px] font-medium", textClass)}>{percentage}%</span>
    </div>
  );
}

// Expandable card component
function ExpandableCard({
  children,
  preview,
  isExpanded,
  onToggle,
  accentColor,
}: {
  children: React.ReactNode;
  preview: React.ReactNode;
  isExpanded: boolean;
  onToggle: () => void;
  accentColor?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg transition-all overflow-hidden group w-full border bg-muted/50",
        isExpanded && "shadow-sm"
      )}
      style={{
        borderColor: isExpanded ? accentColor || "hsl(var(--primary))" : undefined,
      }}
    >
      <div
        className="cursor-pointer transition-colors hover:bg-accent w-full overflow-hidden"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between w-full">
          <div className="flex-1 min-w-0 overflow-hidden">{preview}</div>
          <div className="p-2.5 opacity-50 group-hover:opacity-100 transition-opacity shrink-0">
            {isExpanded ? (
              <ChevronUpIcon className="w-4 h-4" />
            ) : (
              <ChevronDownIcon className="w-4 h-4" />
            )}
          </div>
        </div>
      </div>
      {isExpanded && (
        <div className="w-full overflow-hidden border-t">
          {children}
        </div>
      )}
    </div>
  );
}

export function WorkspacePanel({ chatId, isActive }: WorkspacePanelProps) {
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"tasks" | "findings" | "decisions">("findings");
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const toggleExpanded = (key: string) => {
    setExpandedItems(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const fetchWorkspace = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai/group-chats/${chatId}/workspace`);
      if (res.ok) {
        const data = await res.json();
        setWorkspace(data);
        setLastUpdated(new Date());
      }
    } catch (e) {
      console.error("Failed to fetch workspace:", e);
    } finally {
      setLoading(false);
    }
  }, [chatId]);

  useEffect(() => {
    fetchWorkspace();
    if (isActive) {
      const interval = setInterval(fetchWorkspace, 5000);
      return () => clearInterval(interval);
    }
  }, [fetchWorkspace, isActive]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <div className="absolute inset-0 flex items-center justify-center">
              <LightbulbIcon className="w-3.5 h-3.5 text-primary" />
            </div>
          </div>
          <span className="text-[11px] text-muted-foreground">
            Loading workspace...
          </span>
        </div>
      </div>
    );
  }

  if (!workspace || (workspace.summary.total_tasks === 0 && workspace.summary.total_findings === 0 && workspace.summary.total_decisions === 0)) {
    return (
      <div className="flex flex-col items-center justify-center h-32 text-center px-4">
        <div className="w-10 h-10 rounded-full flex items-center justify-center mb-3 bg-muted">
          <LightbulbIcon className="w-5 h-5 text-muted-foreground" />
        </div>
        <p className="text-[11px] font-medium mb-1 text-muted-foreground">
          No workspace data yet
        </p>
        <p className="text-[10px] text-muted-foreground/70">
          Agents will add findings, tasks, and decisions as they collaborate
        </p>
      </div>
    );
  }

  const tabConfig = [
    {
      key: "findings" as const,
      label: "Findings",
      count: workspace.summary.total_findings,
      icon: LightbulbIcon,
      color: "hsl(var(--primary))",
    },
    {
      key: "tasks" as const,
      label: "Tasks",
      count: workspace.summary.total_tasks,
      icon: CheckCircleIcon,
      color: "hsl(var(--success))",
      subtext: workspace.summary.completed_tasks > 0
        ? `${workspace.summary.completed_tasks}/${workspace.summary.total_tasks}`
        : undefined,
    },
    {
      key: "decisions" as const,
      label: "Decisions",
      count: workspace.summary.total_decisions,
      icon: ScaleIcon,
      color: "hsl(var(--warning))",
      subtext: workspace.summary.approved_decisions > 0
        ? `${workspace.summary.approved_decisions} approved`
        : undefined,
    },
  ];

  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      {/* Summary stats header */}
      <div className="shrink-0 p-3 w-full bg-muted border-b">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Workspace Summary
          </span>
          {lastUpdated && isActive && (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full animate-pulse bg-success" />
              <span className="text-[9px] text-muted-foreground">
                Live
              </span>
            </div>
          )}
        </div>
        <div className="grid grid-cols-3 gap-2">
          {tabConfig.map(({ key, label, count, icon: Icon, color, subtext }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={cn(
                "flex flex-col items-center p-2 rounded-lg transition-all border",
                activeTab === key ? "bg-card shadow-sm" : "bg-background"
              )}
              style={{
                borderColor: activeTab === key ? color : undefined,
              }}
            >
              <Icon className="w-4 h-4 mb-1" style={{ color }} />
              <span className="text-[13px] font-bold text-foreground">
                {count}
              </span>
              <span className="text-[9px] text-muted-foreground">
                {label}
              </span>
              {subtext && (
                <span className="text-[8px] mt-0.5" style={{ color }}>
                  {subtext}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-2 w-full">
        {/* FINDINGS TAB */}
        {activeTab === "findings" && workspace.findings.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <LightbulbIcon className="w-6 h-6 mb-2 text-muted-foreground" />
            <p className="text-[11px] text-muted-foreground">
              No findings yet
            </p>
          </div>
        )}
        {activeTab === "findings" && workspace.findings.map((finding) => {
          const isExpanded = expandedItems.has(finding.finding_key);
          return (
            <ExpandableCard
              key={finding.id}
              isExpanded={isExpanded}
              onToggle={() => toggleExpanded(finding.finding_key)}
              accentColor="hsl(var(--primary))"
              preview={
                <div className="p-3 overflow-hidden w-full">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <div className="flex items-center gap-1.5 flex-1 min-w-0">
                      <Badge variant="info" className="shrink-0 text-[11px]">
                        {finding.category}
                      </Badge>
                      <span className="text-[10px] truncate text-muted-foreground">
                        by @{finding.source_agent}
                      </span>
                    </div>
                    <ConfidenceBar confidence={finding.confidence} />
                  </div>
                  <p className="text-[12px] leading-relaxed line-clamp-3 text-foreground">
                    {finding.content}
                  </p>
                </div>
              }
            >
              <div className="p-3 overflow-hidden w-full">
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="info" className="text-[11px]">
                      {finding.category}
                    </Badge>
                    <span className="text-[10px] text-muted-foreground">
                      by @{finding.source_agent}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <ConfidenceBar confidence={finding.confidence} />
                    <CopyButton text={finding.content} />
                  </div>
                </div>
                <div className="p-3 rounded-lg mb-3 overflow-hidden w-full bg-background">
                  <p className="text-[12px] leading-relaxed break-words text-foreground whitespace-pre-wrap break-all">
                    {finding.content}
                  </p>
                </div>
                <div className="flex items-center justify-between flex-wrap gap-2 w-full">
                  {finding.tags && finding.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-1 flex-1 min-w-0">
                      {finding.tags.map((tag, i) => (
                        <Badge key={i} variant="secondary" className="text-[10px]">
                          #{tag}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <div />
                  )}
                  <span className="text-[9px] font-mono shrink-0 text-muted-foreground">
                    {finding.finding_key}
                  </span>
                </div>
              </div>
            </ExpandableCard>
          );
        })}

        {/* TASKS TAB */}
        {activeTab === "tasks" && workspace.tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <CheckCircleIcon className="w-6 h-6 mb-2 text-muted-foreground" />
            <p className="text-[11px] text-muted-foreground">
              No tasks yet
            </p>
          </div>
        )}
        {activeTab === "tasks" && workspace.tasks.map((task) => {
          const isExpanded = expandedItems.has(task.task_key);
          const statusConfig = {
            completed: { className: "bg-success/10 text-success", label: "Completed", color: "hsl(var(--success))" },
            in_progress: { className: "bg-warning/10 text-warning", label: "In Progress", color: "hsl(var(--warning))" },
            pending: { className: "bg-muted text-muted-foreground", label: "Pending", color: "hsl(var(--muted-foreground))" },
          }[task.status] || { className: "bg-muted text-muted-foreground", label: task.status, color: "hsl(var(--muted-foreground))" };

          return (
            <ExpandableCard
              key={task.id}
              isExpanded={isExpanded}
              onToggle={() => toggleExpanded(task.task_key)}
              accentColor={statusConfig.color}
              preview={
                <div className="p-3 overflow-hidden w-full">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="relative shrink-0">
                      <div className={cn("h-5 w-5 rounded-full flex items-center justify-center", statusConfig.className)}>
                        {task.status === "completed" ? (
                          <CheckIcon className="w-3 h-3" />
                        ) : task.status === "in_progress" ? (
                          <div className="w-2 h-2 rounded-full animate-pulse bg-current" />
                        ) : (
                          <div className="w-2 h-2 rounded-full bg-current" />
                        )}
                      </div>
                    </div>
                    <span className="text-[12px] font-medium flex-1 min-w-0 line-clamp-1 text-foreground">
                      {task.title}
                    </span>
                    {task.result && (
                      <Badge variant="success" className="text-[10px] shrink-0">
                        Has result
                      </Badge>
                    )}
                  </div>
                  <p className="text-[11px] line-clamp-2 ml-7 text-muted-foreground">
                    {task.description.replace(/\[.*?\]\s*/, "")}
                  </p>
                </div>
              }
            >
              <div className="p-3 overflow-hidden w-full">
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <Badge className={cn("text-[10px] uppercase tracking-wide shrink-0", statusConfig.className)}>
                    {statusConfig.label}
                  </Badge>
                  <span className="text-[12px] font-medium flex-1 min-w-0 break-words text-foreground">
                    {task.title}
                  </span>
                </div>

                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Description
                    </span>
                    <CopyButton text={task.description} />
                  </div>
                  <div className="p-3 rounded-lg overflow-hidden w-full bg-background">
                    <p className="text-[12px] leading-relaxed break-words text-foreground whitespace-pre-wrap break-all">
                      {task.description}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4 text-[10px] mb-3 px-1 flex-wrap text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <span className="font-medium">Created:</span>
                    <span>@{task.created_by}</span>
                  </div>
                  {task.assigned_to && (
                    <div className="flex items-center gap-1">
                      <span className="font-medium">Assigned:</span>
                      <span>@{task.assigned_to}</span>
                    </div>
                  )}
                </div>

                {task.result && (
                  <div className="rounded-lg overflow-hidden w-full border border-success">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-success/10">
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-success">
                        Result
                      </span>
                      <CopyButton text={task.result} />
                    </div>
                    <div className="p-3 overflow-hidden w-full bg-background">
                      <p className="text-[12px] leading-relaxed break-words text-foreground whitespace-pre-wrap break-all">
                        {task.result}
                      </p>
                    </div>
                  </div>
                )}

                <div className="mt-3 pt-2 flex justify-end border-t">
                  <span className="text-[9px] font-mono text-muted-foreground">
                    {task.task_key}
                  </span>
                </div>
              </div>
            </ExpandableCard>
          );
        })}

        {/* DECISIONS TAB */}
        {activeTab === "decisions" && workspace.decisions.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <ScaleIcon className="w-6 h-6 mb-2 text-muted-foreground" />
            <p className="text-[11px] text-muted-foreground">
              No decisions yet
            </p>
          </div>
        )}
        {activeTab === "decisions" && workspace.decisions.map((decision) => {
          const isExpanded = expandedItems.has(decision.decision_key);
          const statusConfig = {
            approved: { className: "bg-success/10 text-success", icon: "\u2713", color: "hsl(var(--success))" },
            rejected: { className: "bg-destructive/10 text-destructive", icon: "\u2717", color: "hsl(var(--destructive))" },
            pending: { className: "bg-warning/10 text-warning", icon: "?", color: "hsl(var(--warning))" },
          }[decision.status] || { className: "bg-warning/10 text-warning", icon: "?", color: "hsl(var(--warning))" };

          const votesFor = decision.votes_for?.length || 0;
          const votesAgainst = decision.votes_against?.length || 0;
          const totalVotes = votesFor + votesAgainst;

          return (
            <ExpandableCard
              key={decision.id}
              isExpanded={isExpanded}
              onToggle={() => toggleExpanded(decision.decision_key)}
              accentColor={statusConfig.color}
              preview={
                <div className="p-3 overflow-hidden w-full">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0", statusConfig.className)}>
                      {statusConfig.icon}
                    </div>
                    <span className="text-[12px] font-medium flex-1 min-w-0 line-clamp-1 text-foreground">
                      {decision.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 ml-7 flex-wrap">
                    {/* Vote bar */}
                    {totalVotes > 0 && (
                      <div className="flex items-center gap-1.5 flex-1 min-w-[100px]">
                        <div className="flex-1 h-1.5 rounded-full overflow-hidden flex bg-muted">
                          <div className="h-full bg-success" style={{ width: `${(votesFor / totalVotes) * 100}%` }} />
                          <div className="h-full bg-destructive" style={{ width: `${(votesAgainst / totalVotes) * 100}%` }} />
                        </div>
                        <span className="text-[10px] shrink-0 text-success">+{votesFor}</span>
                        <span className="text-[10px] shrink-0 text-destructive">-{votesAgainst}</span>
                      </div>
                    )}
                    {totalVotes === 0 && (
                      <span className="text-[10px] text-muted-foreground">No votes yet</span>
                    )}
                    <span className="text-[10px] shrink-0 text-muted-foreground">
                      by @{decision.proposed_by}
                    </span>
                  </div>
                </div>
              }
            >
              <div className="p-3 overflow-hidden w-full">
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <Badge className={cn("text-[10px] uppercase tracking-wide shrink-0", statusConfig.className)}>
                    {decision.status}
                  </Badge>
                  <span className="text-[12px] font-medium flex-1 min-w-0 break-words text-foreground">
                    {decision.title}
                  </span>
                </div>

                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Description
                    </span>
                    <CopyButton text={decision.description} />
                  </div>
                  <div className="p-3 rounded-lg overflow-hidden w-full bg-background">
                    <p className="text-[12px] leading-relaxed break-words text-foreground whitespace-pre-wrap break-all">
                      {decision.description}
                    </p>
                  </div>
                </div>

                {decision.rationale && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                        Rationale
                      </span>
                      <CopyButton text={decision.rationale} />
                    </div>
                    <div className="p-3 rounded-lg overflow-hidden w-full bg-background">
                      <p className="text-[12px] leading-relaxed break-words text-foreground whitespace-pre-wrap break-all">
                        {decision.rationale}
                      </p>
                    </div>
                  </div>
                )}

                {/* Votes section */}
                <div className="rounded-lg overflow-hidden w-full border">
                  <div className="grid grid-cols-2">
                    <div className="p-3 border-r">
                      <div className="flex items-center gap-1.5 mb-2">
                        <div className="w-2 h-2 rounded-full shrink-0 bg-success" />
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-success">
                          For ({votesFor})
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {decision.votes_for?.length ? decision.votes_for.map((v, i) => (
                          <Badge key={i} variant="success" className="text-[10px]">
                            @{v}
                          </Badge>
                        )) : (
                          <span className="text-[10px] text-muted-foreground">None</span>
                        )}
                      </div>
                    </div>
                    <div className="p-3">
                      <div className="flex items-center gap-1.5 mb-2">
                        <div className="w-2 h-2 rounded-full shrink-0 bg-destructive" />
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-destructive">
                          Against ({votesAgainst})
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {decision.votes_against?.length ? decision.votes_against.map((v, i) => (
                          <Badge key={i} variant="destructive" className="text-[10px]">
                            @{v}
                          </Badge>
                        )) : (
                          <span className="text-[10px] text-muted-foreground">None</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-3 pt-2 flex items-center justify-between flex-wrap gap-2 border-t">
                  <span className="text-[10px] text-muted-foreground">
                    Proposed by @{decision.proposed_by}
                  </span>
                  <span className="text-[9px] font-mono text-muted-foreground">
                    {decision.decision_key}
                  </span>
                </div>
              </div>
            </ExpandableCard>
          );
        })}
      </div>
    </div>
  );
}
