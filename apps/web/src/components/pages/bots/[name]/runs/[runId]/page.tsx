"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import BotRunLog from "@/components/bot-run-log";
import Markdown from "@/components/markdown";
import type { BotRun, BotLogEntry } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<string, "success" | "destructive" | "warning" | "secondary"> = {
  running: "success",
  completed: "success",
  approved: "success",
  errored: "destructive",
  rejected: "destructive",
  cancelled: "warning",
  awaiting_approval: "warning",
};

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const name = params.name as string;
  const runId = params.runId as string;

  const [run, setRun] = useState<BotRun | null>(null);
  const [logs, setLogs] = useState<BotLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);

  useEffect(() => {
    fetch(`/api/ai/bots/${name}/runs/${runId}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.run) setRun(data.run);
        if (data.logs) setLogs(data.logs);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [name, runId]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Skeleton className="h-6 w-32" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-base font-semibold mb-2 text-foreground">
            Run not found
          </h2>
          <Button variant="ghost" onClick={() => router.push(`/bots/${name}`)} className="text-xs">
            Back to Bot
          </Button>
        </div>
      </div>
    );
  }

  const duration = run.completed_at
    ? ((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1) + "s"
    : "Running...";

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-[1000px] mx-auto p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6 animate-fade-in-up">
          <button
            onClick={() => router.push(`/bots/${name}`)}
            className="p-1.5 rounded-lg transition-colors hover:bg-accent"
          >
            <svg className="h-5 w-5 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-foreground">
                Run {runId.slice(0, 8)}...
              </h1>
              <Badge variant={STATUS_BADGE[run.status] || "secondary"}>
                {run.status}
              </Badge>
            </div>
            <p className="data-mono text-[11px] mt-0.5 text-muted-foreground/70">
              {name.replace(/_/g, " ")} | Trigger: {run.trigger_type}
            </p>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-5 gap-3 mb-6">
          {[
            { label: "Started", value: new Date(run.started_at).toLocaleString() },
            { label: "Duration", value: duration },
            { label: "Input Tokens", value: run.input_tokens.toLocaleString() },
            { label: "Output Tokens", value: run.output_tokens.toLocaleString() },
            { label: "Cost", value: `$${run.cost.toFixed(4)}` },
          ].map((stat) => (
            <Card key={stat.label} className="p-3">
              <p className="text-[9px] uppercase tracking-wider mb-1 text-muted-foreground/70">
                {stat.label}
              </p>
              <p className="data-mono text-sm font-semibold text-foreground">
                {stat.value}
              </p>
            </Card>
          ))}
        </div>

        {/* Output */}
        {run.output && (
          <div className="mb-6">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Output</h2>
            <Card className="p-5 text-sm leading-relaxed text-muted-foreground">
              <Markdown>{run.output}</Markdown>
            </Card>
          </div>
        )}

        {/* Approval actions */}
        {run.status === "awaiting_approval" && (
          <Card className="p-4 mb-6 flex items-center justify-between bg-warning/10 border-warning">
            <div>
              <h3 className="text-sm font-semibold mb-0.5 text-warning">
                Awaiting Your Approval
              </h3>
              <p className="text-[11px] text-muted-foreground">
                Review the output above and approve or reject this bot&apos;s work.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                disabled={approving}
                onClick={async () => {
                  setApproving(true);
                  try {
                    const resp = await fetch(`/api/ai/bots/${name}/runs/${runId}/reject`, { method: "POST" });
                    if (resp.ok) setRun({ ...run, status: "rejected" });
                  } finally { setApproving(false); }
                }}
                variant="ghost"
                className="bg-destructive/10 text-destructive hover:bg-destructive/20 text-xs font-semibold"
              >
                Reject
              </Button>
              <Button
                disabled={approving}
                onClick={async () => {
                  setApproving(true);
                  try {
                    const resp = await fetch(`/api/ai/bots/${name}/runs/${runId}/approve`, { method: "POST" });
                    if (resp.ok) setRun({ ...run, status: "approved" });
                  } finally { setApproving(false); }
                }}
                className="text-xs font-semibold"
              >
                Approve
              </Button>
            </div>
          </Card>
        )}

        {/* Tool Call Timeline */}
        {logs.length > 0 && (() => {
          const toolLogs = logs.filter((l) =>
            l.event_type === "tool_start" || l.event_type === "tool_end" ||
            l.message.toLowerCase().includes("tool") || l.event_type === "agent_start" ||
            l.event_type === "model_resolved" || l.event_type === "run_complete"
          );
          if (toolLogs.length === 0) return null;
          return (
            <div className="mb-6">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Execution Timeline</h2>
              <Card className="p-4">
                <div className="relative pl-5">
                  {/* Vertical line */}
                  <div className="absolute left-[7px] top-1 bottom-1 w-px bg-border" />
                  {toolLogs.map((log, i) => {
                    const isComplete = log.event_type === "run_complete";
                    const isError = log.level === "error";
                    return (
                      <div key={log.id || i} className="relative flex items-start gap-3 mb-3 last:mb-0">
                        <div
                          className={cn(
                            "absolute rounded-full shrink-0 w-2 h-2 -left-4 top-1",
                            isComplete ? "bg-success shadow-[0_0_6px_hsl(var(--success))]" :
                            isError ? "bg-destructive" : "bg-primary"
                          )}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] leading-snug text-muted-foreground">
                            {log.message}
                          </p>
                          <p className="data-mono text-[9px] mt-0.5 text-muted-foreground/70">
                            {new Date(log.created_at).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>
          );
        })()}

        {/* Logs */}
        {logs.length > 0 && (
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Run Logs</h2>
            <BotRunLog logs={logs} maxHeight={400} autoScroll={false} />
          </div>
        )}

        {/* Error details + retry */}
        {(run.status === "errored" || run.status === "cancelled") && (
          <Card className="p-4 flex items-center justify-between bg-destructive/10 mt-6">
            <div>
              <h3 className="text-sm font-semibold mb-0.5 text-destructive">
                Run {run.status === "cancelled" ? "Cancelled" : "Failed"}
              </h3>
              <p className="text-xs text-muted-foreground">
                {run.output ? "See output above." : "Check the logs above for error details."}
              </p>
            </div>
            <Button
              onClick={async () => {
                const resp = await fetch(`/api/ai/bots/${name}/runs/${runId}/retry`, { method: "POST" });
                if (resp.ok) router.push(`/bots/${name}`);
              }}
              variant="ghost"
              className="bg-warning/10 text-warning hover:bg-warning/20 text-xs font-semibold shrink-0"
            >
              Retry
            </Button>
          </Card>
        )}
      </div>
    </div>
  );
}
