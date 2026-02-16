"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { useBotEvents } from "@/lib/use-bot-events";
import BotConfigModal from "@/components/bot-config-modal";
import BotRunLog from "@/components/bot-run-log";
import Markdown from "@/components/markdown";
import type { BotRun, BotState, BotLogEntry } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

interface BotAnalytics {
  total_runs: number;
  success_rate: number;
  error_rate: number;
  avg_duration_s: number;
  avg_cost: number;
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  recent_statuses: string[];
}

const STATUS_BADGE: Record<string, "success" | "destructive" | "warning" | "secondary" | "info"> = {
  running: "success",
  scheduled: "info",
  paused: "warning",
  stopped: "secondary",
  errored: "destructive",
  disabled: "secondary",
  completed: "success",
  cancelled: "warning",
};

export default function BotDetailPage() {
  const params = useParams();
  const router = useRouter();
  const name = params.name as string;

  const botStates = useAppStore((s) => s.botStates);
  const botRunsMap = useAppStore((s) => s.botRuns);
  const setBotRuns = useAppStore((s) => s.setBotRuns);
  const botLogsMap = useAppStore((s) => s.botLogs);
  const [showConfig, setShowConfig] = useState(false);
  const [runs, setRuns] = useState<BotRun[]>([]);
  const [liveLogs, setLiveLogs] = useState<BotLogEntry[]>([]);
  const [analytics, setAnalytics] = useState<BotAnalytics | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareRuns, setCompareRuns] = useState<[BotRun | null, BotRun | null]>([null, null]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchDebounce, setSearchDebounce] = useState<string>("");
  const [showIntegrations, setShowIntegrations] = useState(false);
  const [integrations, setIntegrations] = useState<Record<string, Record<string, unknown>>>({});
  const [savingIntegrations, setSavingIntegrations] = useState(false);
  const [testingNotification, setTestingNotification] = useState(false);
  const [notificationResult, setNotificationResult] = useState<Record<string, { ok: boolean; result?: string; error?: string }> | null>(null);

  useBotEvents();

  const bot = botStates.find((b) => b.name === name);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => setSearchDebounce(searchQuery), 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch bot detail, runs, and analytics
  useEffect(() => {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (searchDebounce) params.set("search", searchDebounce);
    params.set("limit", "50");
    fetch(`/api/ai/bots/${name}/runs?${params}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.runs) {
          setRuns(data.runs);
          setBotRuns(name, data.runs);
        }
      })
      .catch(() => {});
  }, [name, setBotRuns, statusFilter, searchDebounce]);

  useEffect(() => {
    fetch(`/api/ai/bots/${name}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.recent_runs && !statusFilter && !searchDebounce) {
          setRuns(data.recent_runs);
          setBotRuns(name, data.recent_runs);
        }
      })
      .catch(() => {});
    fetch(`/api/ai/bots/${name}/analytics`)
      .then((r) => r.json())
      .then((data) => {
        if (data.total_runs !== undefined) setAnalytics(data);
      })
      .catch(() => {});
  }, [name, setBotRuns, statusFilter, searchDebounce]);

  // Use store runs if available
  useEffect(() => {
    if (botRunsMap[name]?.length) {
      setRuns(botRunsMap[name]);
    }
  }, [botRunsMap, name]);

  const handleAction = async (action: string) => {
    await fetch(`/api/ai/bots/${name}/${action}`, { method: "POST" });
  };

  const handleConfigSave = async (config: Record<string, unknown>) => {
    await fetch(`/api/ai/bots/${name}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
  };

  const formatDuration = (start: string, end: string | null) => {
    if (!end) return "Running...";
    const ms = new Date(end).getTime() - new Date(start).getTime();
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  if (!bot) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-base font-semibold mb-2 text-foreground">
            Bot not found
          </h2>
          <p className="text-xs mb-4 text-muted-foreground/70">
            Bot "{name}" is not loaded. Make sure the AI service is running.
          </p>
          <Button variant="ghost" onClick={() => router.push("/bots")} className="text-xs">
            Back to Bots
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-[1100px] mx-auto p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6 animate-fade-in-up">
          <button
            onClick={() => router.push("/bots")}
            className="p-1.5 rounded-lg transition-colors hover:bg-accent"
          >
            <svg className="h-5 w-5 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-[22px] font-bold text-foreground">
                {bot.display_name}
              </h1>
              <Badge variant={STATUS_BADGE[bot.status] || "secondary"}>
                {bot.status}
              </Badge>
            </div>
            <p className="text-xs mt-0.5 text-muted-foreground/70">
              {bot.description}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setIntegrations(bot.integrations ? { ...bot.integrations } as Record<string, Record<string, unknown>> : {});
                setShowIntegrations(true);
                setNotificationResult(null);
              }}
              className="text-xs gap-1.5"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
              Notifications
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                const resp = await fetch(`/api/ai/bots/${name}/duplicate`, { method: "POST" });
                if (resp.ok) {
                  const data = await resp.json();
                  router.push(`/bots/${data.new_name}`);
                }
              }}
              className="text-xs"
            >
              Duplicate
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowConfig(true)} className="text-xs">
              Configure
            </Button>
            {bot.status === "running" ? (
              <Button variant="ghost" size="sm" onClick={() => handleAction("stop")} className="bg-destructive/10 text-destructive hover:bg-destructive/20 text-xs font-semibold">
                Stop
              </Button>
            ) : (
              <Button size="sm" onClick={() => handleAction("start")} className="text-xs font-semibold">
                Start Now
              </Button>
            )}
            {bot.is_custom && (
              <Button
                variant="ghost"
                size="sm"
                onClick={async () => {
                  if (!confirm(`Delete bot "${bot.display_name}"? This cannot be undone.`)) return;
                  const resp = await fetch(`/api/ai/bots/${name}`, { method: "DELETE" });
                  if (resp.ok) router.push("/bots");
                }}
                className="bg-destructive/10 text-destructive hover:bg-destructive/20 text-xs font-semibold"
              >
                Delete
              </Button>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-4 mb-4">
          {[
            { label: "Total Runs", value: String(analytics?.total_runs ?? bot.total_runs) },
            { label: "Success Rate", value: analytics ? `${analytics.success_rate}%` : "-" },
            { label: "Avg Duration", value: analytics?.avg_duration_s ? `${analytics.avg_duration_s}s` : "-" },
            { label: "Total Cost", value: analytics?.total_cost ? `$${analytics.total_cost.toFixed(4)}` : "$0.00" },
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

        {/* Recent runs indicator + secondary stats */}
        <div className="flex items-center gap-6 mb-6 px-1">
          {analytics?.recent_statuses && analytics.recent_statuses.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] uppercase tracking-wider mr-1 text-muted-foreground/70">
                Last {analytics.recent_statuses.length}
              </span>
              {analytics.recent_statuses.map((status, i) => (
                <div
                  key={i}
                  className={cn(
                    "w-2 h-2 rounded-full",
                    status === "completed" ? "bg-success" :
                    status === "errored" ? "bg-destructive" :
                    status === "cancelled" ? "bg-warning" :
                    "bg-muted-foreground"
                  )}
                  title={status}
                  style={{
                    opacity: 0.3 + 0.7 * ((analytics.recent_statuses.length - i) / analytics.recent_statuses.length),
                  }}
                />
              ))}
            </div>
          )}
          <div className="flex items-center gap-4 text-[11px] text-muted-foreground/70">
            <span>Model: <span className="text-muted-foreground">{bot.config.model || "default"}</span></span>
            <span>Schedule: <span className="text-muted-foreground">
              {bot.config.schedule?.type === "interval"
                ? `Every ${bot.config.schedule.hours}h`
                : `Daily ${String(bot.config.schedule?.hour ?? 0).padStart(2, "0")}:${String(bot.config.schedule?.minute ?? 0).padStart(2, "0")}`}
            </span></span>
            {analytics?.avg_cost ? (
              <span>Avg Cost: <span className="text-primary">${analytics.avg_cost.toFixed(4)}</span></span>
            ) : null}
            {analytics?.total_input_tokens ? (
              <span>Tokens: <span className="text-muted-foreground">{((analytics.total_input_tokens + analytics.total_output_tokens) / 1000).toFixed(1)}k</span></span>
            ) : null}
          </div>
        </div>

        {/* Live log viewer (when running) */}
        {bot.status === "running" && (() => {
          // Find the active run's logs from the store
          const activeRun = runs.find((r) => r.status === "running");
          const activeRunId = activeRun?.run_id;
          const storeLogs = activeRunId ? botLogsMap[activeRunId] || [] : [];
          const displayLogs = storeLogs.length > 0 ? storeLogs : liveLogs;
          return (
            <div className="mb-6">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Live Log</h2>
              <BotRunLog logs={displayLogs} maxHeight={200} />
            </div>
          );
        })()}

        {/* Compare panel */}
        {compareRuns[0] && compareRuns[1] && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Comparing Runs</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setCompareIds([]); setCompareRuns([null, null]); }}
                className="text-[11px]"
              >
                Close
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {compareRuns.map((cr, i) => cr && (
                <Card key={i} className="p-4 overflow-auto max-h-[500px]">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b">
                    <Badge variant={STATUS_BADGE[cr.status] || "secondary"}>
                      {cr.status}
                    </Badge>
                    <span className="data-mono text-[10px] text-muted-foreground/70">
                      {new Date(cr.started_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-xs leading-relaxed text-muted-foreground">
                    <Markdown>{cr.output || "(no output)"}</Markdown>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Run History */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Run History</h2>
            <div className="flex items-center gap-3">
              {/* Status filter */}
              <div className="flex items-center gap-1">
                {["", "completed", "errored", "cancelled", "running", "awaiting_approval"].map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={cn(
                      "px-2 py-1 rounded text-[10px] font-medium transition-colors",
                      statusFilter === s ? "bg-primary/10 text-primary" : "text-muted-foreground/70 hover:text-muted-foreground"
                    )}
                  >
                    {s || "All"}
                  </button>
                ))}
              </div>
              {/* Search */}
              <Input
                type="text"
                placeholder="Search output..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-7 px-2.5 text-[11px] w-40"
              />
              {runs.length >= 2 && (
                <span className="text-[10px] text-muted-foreground/70">
                  {compareIds.length === 0 ? "Select 2 to compare" :
                   compareIds.length === 1 ? "Select 1 more" : ""}
                </span>
              )}
              {runs.length > 0 && (
                <Button variant="ghost" size="sm" asChild className="text-[11px] gap-1.5">
                  <a href={`/api/ai/bots/${name}/runs/export`} download>
                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                    </svg>
                    Export CSV
                  </a>
                </Button>
              )}
            </div>
          </div>
          {runs.length === 0 ? (
            <Card className="p-6 text-center">
              <p className="text-xs text-muted-foreground/70">
                No runs yet. Start the bot to see history.
              </p>
            </Card>
          ) : (
            <Card className="overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    {runs.length >= 2 && (
                      <th className="text-left text-[10px] font-semibold uppercase tracking-wider px-2 py-2.5 w-8 text-muted-foreground/70">
                      </th>
                    )}
                    {["Status", "Trigger", "Started", "Duration", "Tokens", "Cost", ""].map((h) => (
                      <th
                        key={h}
                        className="text-left text-[10px] font-semibold uppercase tracking-wider px-4 py-2.5 text-muted-foreground/70"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.run_id}
                      className={cn(
                        "cursor-pointer transition-colors hover:bg-accent border-b",
                        compareIds.includes(run.run_id) && "bg-primary/5"
                      )}
                      onClick={() => router.push(`/bots/${name}/runs/${run.run_id}`)}
                    >
                      {runs.length >= 2 && (
                        <td className="px-2 py-2.5 w-8">
                          <input
                            type="checkbox"
                            checked={compareIds.includes(run.run_id)}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              e.stopPropagation();
                              setCompareIds((prev) => {
                                if (prev.includes(run.run_id)) {
                                  const next = prev.filter((id) => id !== run.run_id);
                                  setCompareRuns([null, null]);
                                  return next;
                                }
                                if (prev.length >= 2) return prev;
                                const next = [...prev, run.run_id];
                                if (next.length === 2) {
                                  // Fetch both runs' full output
                                  Promise.all(
                                    next.map((id) =>
                                      fetch(`/api/ai/bots/${name}/runs/${id}`)
                                        .then((r) => r.json())
                                        .then((d) => d.run as BotRun | null)
                                        .catch(() => null)
                                    )
                                  ).then(([a, b]) => setCompareRuns([a, b]));
                                }
                                return next;
                              });
                            }}
                            className="rounded accent-primary"
                          />
                        </td>
                      )}
                      <td className="px-4 py-2.5">
                        <Badge variant={STATUS_BADGE[run.status] || "secondary"}>
                          {run.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">
                        {run.trigger_type}
                      </td>
                      <td className="px-4 py-2.5 data-mono text-[11px] text-muted-foreground">
                        {new Date(run.started_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 data-mono text-[11px] text-muted-foreground">
                        {formatDuration(run.started_at, run.completed_at)}
                      </td>
                      <td className="px-4 py-2.5 data-mono text-[11px] text-muted-foreground">
                        {run.input_tokens + run.output_tokens > 0 ? `${((run.input_tokens + run.output_tokens) / 1000).toFixed(1)}k` : "-"}
                      </td>
                      <td className="px-4 py-2.5 data-mono text-[11px] text-primary">
                        {run.cost > 0 ? `$${run.cost.toFixed(4)}` : "-"}
                      </td>
                      <td className="px-4 py-2.5">
                        <svg className="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                        </svg>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      </div>

      {showConfig && (
        <BotConfigModal
          bot={bot}
          onClose={() => setShowConfig(false)}
          onSave={handleConfigSave}
        />
      )}

      {/* Notification Preferences Modal */}
      {showIntegrations && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setShowIntegrations(false)}
        >
          <Card
            className="w-[550px] max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 pb-3">
              <div>
                <h3 className="text-base font-bold text-foreground">
                  Notification Channels
                </h3>
                <p className="text-[11px] mt-0.5 text-muted-foreground/70">
                  Configure where {bot.display_name} sends notifications
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowIntegrations(false)} className="text-[11px]">
                Close
              </Button>
            </div>

            <div className="px-5 space-y-4">
              {["telegram", "slack", "discord", "webhook"].map((channel) => {
                const cfg = (integrations[channel] || {}) as Record<string, unknown>;
                const isEnabled = !!cfg.enabled;
                return (
                  <div
                    key={channel}
                    className={cn(
                      "rounded-lg p-3 bg-card border",
                      isEnabled && "border-primary"
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold capitalize text-foreground">
                          {channel}
                        </span>
                        {isEnabled && (
                          <Badge variant="success">Active</Badge>
                        )}
                      </div>
                      <Switch
                        checked={isEnabled}
                        onCheckedChange={() => {
                          setIntegrations((prev) => ({
                            ...prev,
                            [channel]: { ...cfg, enabled: !isEnabled },
                          }));
                        }}
                      />
                    </div>
                    {isEnabled && (
                      <div className="space-y-2">
                        {channel === "telegram" && (
                          <>
                            <Input
                              type="text"
                              placeholder="Bot token"
                              value={(cfg.bot_token as string) || ""}
                              onChange={(e) => setIntegrations((prev) => ({
                                ...prev,
                                [channel]: { ...cfg, bot_token: e.target.value },
                              }))}
                              className="h-8 text-[11px]"
                            />
                            <Input
                              type="text"
                              placeholder="Chat ID"
                              value={(cfg.chat_id as string) || ""}
                              onChange={(e) => setIntegrations((prev) => ({
                                ...prev,
                                [channel]: { ...cfg, chat_id: e.target.value },
                              }))}
                              className="h-8 text-[11px]"
                            />
                          </>
                        )}
                        {channel === "slack" && (
                          <Input
                            type="text"
                            placeholder="Webhook URL"
                            value={(cfg.webhook_url as string) || ""}
                            onChange={(e) => setIntegrations((prev) => ({
                              ...prev,
                              [channel]: { ...cfg, webhook_url: e.target.value },
                            }))}
                            className="h-8 text-[11px]"
                          />
                        )}
                        {channel === "discord" && (
                          <Input
                            type="text"
                            placeholder="Webhook URL"
                            value={(cfg.webhook_url as string) || ""}
                            onChange={(e) => setIntegrations((prev) => ({
                              ...prev,
                              [channel]: { ...cfg, webhook_url: e.target.value },
                            }))}
                            className="h-8 text-[11px]"
                          />
                        )}
                        {channel === "webhook" && (
                          <>
                            <Input
                              type="text"
                              placeholder="Webhook URL"
                              value={(cfg.url as string) || ""}
                              onChange={(e) => setIntegrations((prev) => ({
                                ...prev,
                                [channel]: { ...cfg, url: e.target.value },
                              }))}
                              className="h-8 text-[11px]"
                            />
                            <Input
                              type="text"
                              placeholder="Authorization header (optional)"
                              value={(cfg.auth_header as string) || ""}
                              onChange={(e) => setIntegrations((prev) => ({
                                ...prev,
                                [channel]: { ...cfg, auth_header: e.target.value },
                              }))}
                              className="h-8 text-[11px]"
                            />
                          </>
                        )}
                      </div>
                    )}
                    {/* Per-channel test result */}
                    {notificationResult?.[channel] && (
                      <div
                        className={cn(
                          "mt-2 rounded px-2 py-1.5 text-[10px]",
                          notificationResult[channel].ok
                            ? "bg-success/10 text-success"
                            : "bg-destructive/10 text-destructive"
                        )}
                      >
                        {notificationResult[channel].ok ? "Delivered" : notificationResult[channel].error}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between p-5 pt-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={async () => {
                  setTestingNotification(true);
                  setNotificationResult(null);
                  try {
                    // Save first, then test
                    await fetch(`/api/ai/bots/${name}/integrations`, {
                      method: "PUT",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ integrations }),
                    });
                    const resp = await fetch(`/api/ai/bots/${name}/test-notification`, { method: "POST" });
                    const data = await resp.json();
                    setNotificationResult(data.results || {});
                  } catch {
                    setNotificationResult({ _error: { ok: false, error: "Request failed" } });
                  } finally {
                    setTestingNotification(false);
                  }
                }}
                disabled={testingNotification}
                className="text-xs gap-1.5"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
                {testingNotification ? "Testing..." : "Test Notifications"}
              </Button>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setShowIntegrations(false)} className="text-xs">
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={savingIntegrations}
                  onClick={async () => {
                    setSavingIntegrations(true);
                    try {
                      await fetch(`/api/ai/bots/${name}/integrations`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ integrations }),
                      });
                      setShowIntegrations(false);
                    } catch {} finally {
                      setSavingIntegrations(false);
                    }
                  }}
                  className="text-xs font-semibold"
                >
                  {savingIntegrations ? "Saving..." : "Save"}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
