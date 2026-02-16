"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { useBotEvents } from "@/lib/use-bot-events";
import BotCard from "@/components/bot-card";
import TokenUsagePanel from "@/components/token-usage-panel";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

interface Toast {
  id: string;
  type: "success" | "error" | "info";
  message: string;
  bot?: string;
}

function SkeletonCard() {
  return (
    <Card className="p-4 min-h-[180px]">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-40 mt-2" />
        </div>
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {[1, 2, 3].map((i) => (
          <div key={i}>
            <Skeleton className="h-2 w-10 mb-1" />
            <Skeleton className="h-4 w-14" />
          </div>
        ))}
      </div>
      <div className="flex gap-1.5">
        <Skeleton className="flex-1 h-8 rounded-lg" />
        <Skeleton className="w-16 h-8 rounded-lg" />
      </div>
    </Card>
  );
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-6 right-6 z-50 space-y-2 max-w-[360px]">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "rounded-lg px-4 py-3 text-xs font-medium animate-slide-in-right flex items-center gap-2 shadow-lg cursor-pointer border",
            toast.type === "success" && "bg-success/10 text-success border-success/20",
            toast.type === "error" && "bg-destructive/10 text-destructive border-destructive/20",
            toast.type === "info" && "bg-primary/10 text-primary border-primary/20"
          )}
          onClick={() => onDismiss(toast.id)}
        >
          <span className="flex-1">{toast.message}</span>
          <svg className="h-3.5 w-3.5 shrink-0 opacity-60" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
      ))}
    </div>
  );
}

export default function BotsPage() {
  const router = useRouter();
  const botStates = useAppStore((s) => s.botStates);
  const tokenUsage = useAppStore((s) => s.tokenUsage);
  const setBotStates = useAppStore((s) => s.setBotStates);
  const setTokenUsage = useAppStore((s) => s.setTokenUsage);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [filter, setFilter] = useState("");
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [showYamlEditor, setShowYamlEditor] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlSaving, setYamlSaving] = useState(false);
  const [activityLog, setActivityLog] = useState<{ type: string; bot_name: string; message: string; time: string; cost?: number }[]>([]);
  const [page, setPage] = useState(0);
  const BOTS_PER_PAGE = 9;
  const [showTriggerMap, setShowTriggerMap] = useState(false);
  const [triggerMap, setTriggerMap] = useState<{ nodes: { id: string; display_name: string; triggers: string[]; schedule?: string | null }[]; edges: { from: string; to: string; type: string; label: string }[] } | null>(null);
  const [showCalendar, setShowCalendar] = useState(false);
  const [calendarEntries, setCalendarEntries] = useState<{ bot_name: string; display_name: string; time: string; type: string; status: string }[]>([]);

  // Connect to SSE
  useBotEvents();

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      if (e.shiftKey && e.key === "S") { e.preventDefault(); handleStartAll(); }
      if (e.shiftKey && e.key === "X") { e.preventDefault(); handleStopAll(); }
      if (e.shiftKey && e.key === "N") { e.preventDefault(); router.push("/bots/create"); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const addToast = useCallback((type: Toast["type"], message: string, bot?: string) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, type, message, bot }].slice(-5));
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Initial data fetch
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [botsRes, usageRes] = await Promise.allSettled([
          fetch("/api/ai/bots").then((r) => r.json()),
          fetch("/api/ai/bots/token-usage").then((r) => r.json()),
        ]);

        if (botsRes.status === "fulfilled" && botsRes.value.bots) {
          setBotStates(botsRes.value.bots);
        } else {
          setError("Failed to load bots. Is the AI service running?");
        }

        if (usageRes.status === "fulfilled" && usageRes.value.total_cost !== undefined) {
          setTokenUsage(usageRes.value);
        }
      } catch {
        setError("Failed to connect to AI service.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [setBotStates, setTokenUsage]);

  const runningCount = botStates.filter((b) => b.status === "running").length;
  const totalCost = tokenUsage?.total_cost ?? 0;

  const handleBotAction = async (name: string, action: string) => {
    try {
      const res = await fetch(`/api/ai/bots/${name}/${action}`, { method: "POST" });
      const data = await res.json();
      if (data.error) {
        addToast("error", `${name}: ${data.error}`, name);
        return;
      }
      addToast("success", `${name.replace(/_/g, " ")}: ${action}ed`, name);
      setActivityLog((prev) => [
        { type: action, bot_name: name, message: `${action} ${name}`, time: new Date().toISOString() },
        ...prev,
      ].slice(0, 50));
    } catch {
      addToast("error", `Failed to ${action} ${name.replace(/_/g, " ")}`, name);
    }
  };

  const handleStartAll = async () => {
    try {
      await fetch("/api/ai/bots/start-all", { method: "POST" });
      addToast("info", "Starting all bots...");
    } catch {
      addToast("error", "Failed to start all bots");
    }
  };

  const handleStopAll = async () => {
    try {
      await fetch("/api/ai/bots/stop-all", { method: "POST" });
      addToast("info", "Stopping all bots...");
      setShowKillConfirm(false);
    } catch {
      addToast("error", "Failed to stop all bots");
    }
  };

  const filteredBots = filter
    ? botStates.filter((b) =>
        b.display_name.toLowerCase().includes(filter.toLowerCase()) ||
        b.name.toLowerCase().includes(filter.toLowerCase()) ||
        b.status.includes(filter.toLowerCase())
      )
    : botStates;

  const totalPages = Math.max(1, Math.ceil(filteredBots.length / BOTS_PER_PAGE));
  const clampedPage = Math.min(page, totalPages - 1);
  const paginatedBots = filteredBots.slice(clampedPage * BOTS_PER_PAGE, (clampedPage + 1) * BOTS_PER_PAGE);

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-[1400px] mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 animate-fade-in-up">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Bot Control Plane
            </h1>
            <p className="text-sm mt-1 text-muted-foreground/70">
              Autonomous bots working 24/7 on your job search
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Search/filter */}
            <Input
              type="text"
              placeholder="Filter bots..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="h-8 px-3 text-xs w-36"
            />

            {runningCount > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-success/10">
                <span className="h-2 w-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_hsl(var(--success))]" />
                <span className="data-mono text-xs font-semibold text-success">
                  {runningCount} running
                </span>
              </div>
            )}

            <div className="px-3 py-1.5 rounded-lg bg-primary/10">
              <span className="data-mono text-xs font-semibold text-primary">
                ${totalCost.toFixed(4)} total
              </span>
            </div>

            <Button
              variant="ghost"
              size="icon"
              onClick={async () => {
                const resp = await fetch("/api/ai/bots/trigger-map");
                const data = await resp.json();
                setTriggerMap(data);
                setShowTriggerMap(true);
              }}
              title="Bot trigger chain"
              className="h-8 w-8"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
              </svg>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={async () => {
                const resp = await fetch("/api/ai/bots/calendar?days=7");
                const data = await resp.json();
                setCalendarEntries(data.entries || []);
                setShowCalendar(true);
              }}
              title="Schedule calendar"
              className="h-8 w-8"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
              </svg>
            </Button>
            <Button
              onClick={() => router.push("/bots/create")}
              className="text-xs font-semibold gap-1.5"
              size="sm"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Create Bot
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={async () => {
                const resp = await fetch("/api/ai/config/bots");
                const data = await resp.json();
                setYamlText(data.yaml || "");
                setShowYamlEditor(true);
              }}
              title="Edit bots.yaml"
              className="h-8 w-8"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </Button>
            <Button onClick={handleStartAll} size="sm" className="text-xs font-semibold">
              Start All
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => runningCount > 0 ? setShowKillConfirm(true) : handleStopAll()}
              className="text-xs font-semibold"
            >
              Stop All
            </Button>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <Card className="p-4 mb-6 bg-destructive/10 border-destructive">
            <p className="text-sm font-medium text-destructive">{error}</p>
            <button
              onClick={() => { setError(null); setLoading(true); window.location.reload(); }}
              className="mt-2 text-[11px] underline text-destructive"
            >
              Retry
            </button>
          </Card>
        )}

        {/* Bot Activity Status */}
        {!loading && (() => {
          const inCooldown = botStates
            .filter((b) => b.cooldown_until && new Date(b.cooldown_until).getTime() > Date.now() && b.status !== "stopped" && b.status !== "disabled")
            .sort((a, b) => new Date(a.cooldown_until!).getTime() - new Date(b.cooldown_until!).getTime())
            .slice(0, 5);
          const waiting = botStates
            .filter((b) => b.status === "waiting" && !b.cooldown_until)
            .slice(0, 5);
          const shown = [...inCooldown, ...waiting].slice(0, 5);
          if (shown.length === 0) return null;
          return (
            <div className="mb-5 flex items-center gap-4 px-1">
              <span className="text-[9px] uppercase tracking-wider shrink-0 text-muted-foreground/70">
                Status
              </span>
              <div className="flex items-center gap-3 overflow-x-auto">
                {shown.map((b) => {
                  let label = "Waiting for events...";
                  if (b.cooldown_until && new Date(b.cooldown_until).getTime() > Date.now()) {
                    const diff = new Date(b.cooldown_until).getTime() - Date.now();
                    const mins = Math.max(0, Math.floor(diff / 60000));
                    const hrs = Math.floor(mins / 60);
                    label = hrs > 0 ? `cooldown ${hrs}h ${mins % 60}m` : `cooldown ${mins}m`;
                  }
                  return (
                    <div
                      key={b.name}
                      className="flex items-center gap-1.5 shrink-0 rounded-lg px-2.5 py-1.5 cursor-pointer transition-colors bg-card border hover:bg-accent"
                      onClick={() => router.push(`/bots/${b.name}`)}
                    >
                      <span className={cn("h-1.5 w-1.5 rounded-full", b.cooldown_until ? "bg-muted-foreground" : "bg-primary")} />
                      <span className="text-[11px] font-medium text-muted-foreground">
                        {b.display_name}
                      </span>
                      <span className="data-mono text-[10px] text-muted-foreground/70">
                        {label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Bot Grid */}
          <div className="lg:col-span-3">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 stagger">
              {loading ? (
                <>
                  {[1, 2, 3, 4, 5, 6, 7].map((i) => <SkeletonCard key={i} />)}
                </>
              ) : paginatedBots.length > 0 ? (
                paginatedBots.map((bot) => (
                  <BotCard
                    key={bot.name}
                    bot={bot}
                    onStart={() => handleBotAction(bot.name, "start")}
                    onStop={() => handleBotAction(bot.name, "stop")}
                    onPause={() => handleBotAction(bot.name, "pause")}
                    onResume={() => handleBotAction(bot.name, "resume")}
                    onToggleEnabled={(enabled) => {
                      fetch(`/api/ai/bots/${bot.name}/enabled`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ enabled }),
                      });
                    }}
                    onClick={() => router.push(`/bots/${bot.name}`)}
                  />
                ))
              ) : (
                <Card className="col-span-full p-8 text-center">
                  {filter ? (
                    <>
                      <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl mb-3 bg-primary/10">
                        <svg className="h-6 w-6 text-primary" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                        </svg>
                      </div>
                      <h3 className="text-sm font-semibold mb-1 text-foreground">
                        No bots match &ldquo;{filter}&rdquo;
                      </h3>
                      <p className="text-xs text-muted-foreground/70">
                        Try a different search term.
                      </p>
                    </>
                  ) : (
                    <>
                      <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl mb-4 bg-gradient-to-br from-primary/10 to-blue-500/15 border border-primary/20">
                        <svg className="h-8 w-8 text-primary" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />
                        </svg>
                      </div>
                      <h3 className="text-base font-bold mb-2 text-foreground">
                        Your Bot Fleet Awaits
                      </h3>
                      <p className="text-sm max-w-md mx-auto mb-5 text-muted-foreground/70">
                        Create autonomous bots that scout jobs, tailor resumes, draft outreach, and prep interviews — all on autopilot.
                        Connect Telegram, Slack, or webhooks for real-time notifications.
                      </p>
                      <div className="flex items-center justify-center gap-3">
                        <Button
                          onClick={() => router.push("/bots/create")}
                          className="text-sm font-semibold gap-2"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                          </svg>
                          Create Your First Bot
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => { setError(null); setLoading(true); window.location.reload(); }}
                          className="text-sm"
                        >
                          Retry Connection
                        </Button>
                      </div>
                      <p className="text-[11px] mt-4 text-muted-foreground/70">
                        Or start the AI service with <code className="data-mono px-1 py-0.5 rounded bg-muted">bots.yaml</code> to load built-in bots
                      </p>
                    </>
                  )}
                </Card>
              )}
            </div>

            {/* Pagination */}
            {filteredBots.length > BOTS_PER_PAGE && (
              <div className="flex items-center justify-between mt-5 px-1">
                <p className="text-[11px] text-muted-foreground/70">
                  Showing {clampedPage * BOTS_PER_PAGE + 1}–{Math.min((clampedPage + 1) * BOTS_PER_PAGE, filteredBots.length)} of {filteredBots.length} bots
                </p>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={clampedPage === 0}
                    className="text-xs gap-1"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                    Prev
                  </Button>
                  {Array.from({ length: totalPages }, (_, i) => (
                    <Button
                      key={i}
                      variant={i === clampedPage ? "default" : "outline"}
                      size="sm"
                      onClick={() => setPage(i)}
                      className="h-8 w-8 p-0 text-xs"
                    >
                      {i + 1}
                    </Button>
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={clampedPage >= totalPages - 1}
                    className="text-xs gap-1"
                  >
                    Next
                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-4">
            <TokenUsagePanel usage={tokenUsage} />

            {/* Live Activity Feed */}
            <Card className="p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Live Activity</h3>
              <div className="space-y-2 max-h-[300px] overflow-auto">
                {activityLog.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground/70">
                    No activity yet. Start a bot to see live updates.
                  </p>
                ) : (
                  activityLog.map((entry, i) => {
                    const typeConfig: Record<string, { colorClass: string; icon: string }> = {
                      start: { colorClass: "text-success", icon: "\u25B6" },
                      stop: { colorClass: "text-destructive", icon: "\u25A0" },
                      pause: { colorClass: "text-warning", icon: "\u23F8" },
                      resume: { colorClass: "text-primary", icon: "\u25B6" },
                      complete: { colorClass: "text-success", icon: "\u2713" },
                      error: { colorClass: "text-destructive", icon: "\u2717" },
                    };
                    const cfg = typeConfig[entry.type] || { colorClass: "text-primary", icon: "\u2022" };
                    return (
                      <div
                        key={i}
                        className="flex items-start gap-2 cursor-pointer rounded-lg px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent"
                        onClick={() => router.push(`/bots/${entry.bot_name}`)}
                      >
                        <span className={cn("text-[9px] mt-0.5 shrink-0 w-3 text-center", cfg.colorClass)}>
                          {cfg.icon}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] truncate text-muted-foreground">
                            <span className="font-semibold text-foreground">
                              {entry.bot_name.replace(/_/g, " ")}
                            </span>
                            {" "}{entry.message || entry.type}
                          </p>
                          <p className="data-mono text-[9px] text-muted-foreground/70">
                            {new Date(entry.time).toLocaleTimeString()}
                            {entry.cost ? ` · $${Number(entry.cost).toFixed(4)}` : ""}
                          </p>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* Kill switch confirmation dialog */}
      {showKillConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setShowKillConfirm(false)}
        >
          <Card className="w-[380px]" onClick={(e) => e.stopPropagation()}>
            <div className="p-5">
              <h3 className="text-base font-bold mb-2 text-foreground">
                Stop All Bots?
              </h3>
              <p className="text-sm text-muted-foreground/70">
                This will cancel {runningCount} running bot{runningCount !== 1 ? "s" : ""} and pause all schedules.
                Active runs will be terminated immediately.
              </p>
            </div>
            <div className="flex justify-end gap-2 p-5 pt-0">
              <Button variant="ghost" size="sm" onClick={() => setShowKillConfirm(false)} className="text-xs">
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleStopAll}
                className="text-xs font-semibold"
              >
                Stop All Bots
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* YAML Editor Modal */}
      {showYamlEditor && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
          onClick={() => setShowYamlEditor(false)}
        >
          <Card
            className="w-[700px] max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 pb-3">
              <h3 className="text-base font-bold text-foreground">
                Edit bots.yaml
              </h3>
              <Button variant="ghost" size="sm" onClick={() => setShowYamlEditor(false)} className="text-[11px]">
                Close
              </Button>
            </div>
            <div className="flex-1 overflow-auto px-5">
              <textarea
                value={yamlText}
                onChange={(e) => setYamlText(e.target.value)}
                className="w-full h-[400px] rounded-lg p-3 data-mono text-[11px] leading-relaxed resize-none bg-background text-foreground border"
                spellCheck={false}
              />
            </div>
            <div className="flex items-center justify-between p-5 pt-3">
              <p className="text-[10px] text-muted-foreground/70">
                Changes take effect immediately after save. Running bots are not affected.
              </p>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setShowYamlEditor(false)} className="text-xs">
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={yamlSaving}
                  onClick={async () => {
                    setYamlSaving(true);
                    try {
                      const resp = await fetch("/api/ai/config/bots", {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ yaml_text: yamlText }),
                      });
                      const data = await resp.json();
                      if (data.ok) {
                        addToast("success", `Config saved: ${data.bots?.length || 0} bots loaded`);
                        setShowYamlEditor(false);
                        window.location.reload();
                      } else {
                        addToast("error", data.error || "Failed to save config");
                      }
                    } catch {
                      addToast("error", "Failed to save config");
                    } finally {
                      setYamlSaving(false);
                    }
                  }}
                  className="text-xs font-semibold"
                >
                  {yamlSaving ? "Saving..." : "Save & Reload"}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Trigger Map Modal */}
      {showTriggerMap && triggerMap && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
          onClick={() => setShowTriggerMap(false)}
        >
          <Card
            className="w-[750px] max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 pb-3">
              <div>
                <h3 className="text-base font-bold text-foreground">
                  Bot Trigger Chain
                </h3>
                <p className="text-[11px] mt-0.5 text-muted-foreground/70">
                  How bots trigger each other through events
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowTriggerMap(false)} className="text-[11px]">
                Close
              </Button>
            </div>
            <div className="px-5 pb-5">
              {/* Visual chain diagram */}
              <div className="space-y-3">
                {(triggerMap.nodes || []).map((node) => {
                  const outgoing = (triggerMap.edges || []).filter((e) => e.from === node.id);
                  const incoming = (triggerMap.edges || []).filter((e) => e.to === node.id);
                  return (
                    <div
                      key={node.id}
                      className={cn(
                        "rounded-lg p-3 flex items-center gap-4 bg-card border",
                        (outgoing.length > 0 || incoming.length > 0) && "border-primary"
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-semibold text-foreground">
                            {node.display_name}
                          </span>
                          {node.schedule && (
                            <Badge variant="info">
                              {node.schedule}
                            </Badge>
                          )}
                        </div>
                        {node.triggers.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {node.triggers.map((t, i) => (
                              <Badge key={i} variant="warning" className="text-[9px]">
                                on: {t}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="shrink-0 flex flex-col gap-1">
                        {outgoing.map((edge, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-[10px]">
                            <svg className="h-3 w-3 text-primary" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                            </svg>
                            <span className="text-muted-foreground">
                              {(triggerMap.nodes || []).find((n) => n.id === edge.to)?.display_name || edge.to}
                            </span>
                            <span className="text-[8px] text-muted-foreground/70">
                              ({edge.label})
                            </span>
                          </div>
                        ))}
                        {incoming.map((edge, i) => (
                          <div key={`in-${i}`} className="flex items-center gap-1.5 text-[10px]">
                            <svg className="h-3 w-3 text-success" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                            </svg>
                            <span className="text-muted-foreground">
                              from {(triggerMap.nodes || []).find((n) => n.id === edge.from)?.display_name || edge.from}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              {(!triggerMap.edges || triggerMap.edges.length === 0) && (
                <p className="text-center text-xs mt-4 py-6 text-muted-foreground/70">
                  No trigger chains configured. Add <code className="data-mono px-1 py-0.5 rounded bg-muted">trigger_on</code> to bots.yaml to create chains.
                </p>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Calendar Modal -- Weekly Grid View */}
      {showCalendar && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => setShowCalendar(false)}
        >
          <div
            className="w-[96vw] max-w-[1200px] max-h-[90vh] flex flex-col rounded-2xl overflow-hidden bg-card border shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-gradient-to-br from-primary/10 to-blue-500/15">
                  <svg className="h-4.5 w-4.5 text-primary" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-base font-bold text-foreground">
                    Schedule Calendar
                  </h3>
                  <p className="text-[11px] mt-0.5 text-muted-foreground/70">
                    {calendarEntries.length} scheduled runs across 7 days
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {/* Bot color legend */}
                {(() => {
                  const uniqueBots = [...new Set(calendarEntries.map((e) => e.bot_name))];
                  const botColors = [
                    "#58A6FF", "#7C5CFC", "#56D364", "#F0883E", "#FF6B8A",
                    "#39D2C0", "#E5C07B", "#FF79C6", "#8BE9FD", "#BD93F9",
                  ];
                  return (
                    <div className="flex items-center gap-2 flex-wrap justify-end max-w-[500px]">
                      {uniqueBots.slice(0, 8).map((name, i) => {
                        const entry = calendarEntries.find((e) => e.bot_name === name);
                        return (
                          <div key={name} className="flex items-center gap-1.5">
                            <span
                              className="h-2 w-2 rounded-sm"
                              style={{ background: botColors[i % botColors.length] }}
                            />
                            <span className="text-[9px] font-medium text-muted-foreground/70">
                              {entry?.display_name || name.replace(/_/g, " ")}
                            </span>
                          </div>
                        );
                      })}
                      {uniqueBots.length > 8 && (
                        <span className="text-[9px] text-muted-foreground/70">
                          +{uniqueBots.length - 8} more
                        </span>
                      )}
                    </div>
                  );
                })()}
                <button
                  onClick={() => setShowCalendar(false)}
                  className="flex items-center justify-center h-8 w-8 rounded-lg transition-colors hover:bg-accent text-muted-foreground"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Calendar Grid */}
            <div className="flex-1 overflow-auto">
              {(() => {
                const now = new Date();
                const botColors = [
                  "#58A6FF", "#7C5CFC", "#56D364", "#F0883E", "#FF6B8A",
                  "#39D2C0", "#E5C07B", "#FF79C6", "#8BE9FD", "#BD93F9",
                ];
                const uniqueBots = [...new Set(calendarEntries.map((e) => e.bot_name))];
                const botColorMap: Record<string, string> = {};
                uniqueBots.forEach((name, i) => { botColorMap[name] = botColors[i % botColors.length]; });

                // Generate 7 days starting from today
                const days: Date[] = [];
                for (let i = 0; i < 7; i++) {
                  const d = new Date(now);
                  d.setDate(d.getDate() + i);
                  d.setHours(0, 0, 0, 0);
                  days.push(d);
                }

                // Group entries by day index
                const byDayIdx: Record<number, typeof calendarEntries> = {};
                for (const entry of calendarEntries) {
                  const entryDate = new Date(entry.time);
                  for (let i = 0; i < 7; i++) {
                    if (entryDate.toDateString() === days[i].toDateString()) {
                      if (!byDayIdx[i]) byDayIdx[i] = [];
                      byDayIdx[i].push(entry);
                      break;
                    }
                  }
                }

                // Time axis: find min/max hours that have events, clamp to reasonable range
                let minHour = 23, maxHour = 0;
                for (const entry of calendarEntries) {
                  const h = new Date(entry.time).getHours();
                  if (h < minHour) minHour = h;
                  if (h > maxHour) maxHour = h;
                }
                if (calendarEntries.length === 0) { minHour = 6; maxHour = 22; }
                minHour = Math.max(0, minHour - 1);
                maxHour = Math.min(23, maxHour + 1);
                const hours: number[] = [];
                for (let h = minHour; h <= maxHour; h++) hours.push(h);

                const HOUR_HEIGHT = 56;
                const nowHour = now.getHours() + now.getMinutes() / 60;

                if (calendarEntries.length === 0) {
                  return (
                    <div className="flex flex-col items-center justify-center py-20">
                      <div className="flex items-center justify-center h-16 w-16 rounded-2xl mb-4 bg-muted">
                        <svg className="h-8 w-8 text-muted-foreground/40" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                        </svg>
                      </div>
                      <p className="text-sm font-semibold mb-1 text-foreground">
                        No scheduled runs
                      </p>
                      <p className="text-xs text-muted-foreground/70">
                        Enable bots or configure schedules to see upcoming runs
                      </p>
                    </div>
                  );
                }

                return (
                  <div className="flex" style={{ minHeight: hours.length * HOUR_HEIGHT + 60 }}>
                    {/* Time gutter */}
                    <div className="shrink-0 w-14 border-r">
                      {/* Day header spacer */}
                      <div style={{ height: 52 }} />
                      {/* Hour labels */}
                      <div className="relative">
                        {hours.map((h) => (
                          <div
                            key={h}
                            className="flex items-start justify-end pr-3"
                            style={{ height: HOUR_HEIGHT }}
                          >
                            <span className="data-mono text-[10px] -mt-[6px] text-muted-foreground/70">
                              {h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Day columns */}
                    <div className="flex-1 flex">
                      {days.map((day, dayIdx) => {
                        const isToday = day.toDateString() === now.toDateString();
                        const dayEntries = byDayIdx[dayIdx] || [];
                        const dayName = day.toLocaleDateString("en-US", { weekday: "short" });
                        const dayNum = day.getDate();
                        const monthName = day.toLocaleDateString("en-US", { month: "short" });

                        return (
                          <div
                            key={dayIdx}
                            className={cn(
                              "flex-1 min-w-0",
                              dayIdx < 6 && "border-r",
                              isToday && "bg-primary/[0.02]"
                            )}
                          >
                            {/* Day header */}
                            <div
                              className={cn(
                                "flex flex-col items-center justify-center sticky top-0 z-10 py-2 border-b",
                                isToday ? "bg-gradient-to-b from-primary/[0.08] to-primary/[0.02]" : "bg-card"
                              )}
                              style={{ height: 52 }}
                            >
                              <span className={cn(
                                "text-[10px] font-semibold uppercase tracking-wider",
                                isToday ? "text-primary" : "text-muted-foreground/70"
                              )}>
                                {dayName}
                              </span>
                              <div className="flex items-center gap-1">
                                <span className={cn(
                                  "text-base font-bold flex items-center justify-center",
                                  isToday && "rounded-full bg-primary text-primary-foreground w-7 h-7 text-sm"
                                )}>
                                  {dayNum}
                                </span>
                                {(dayIdx === 0 || dayNum === 1) && (
                                  <span className="text-[9px] text-muted-foreground/70">
                                    {monthName}
                                  </span>
                                )}
                              </div>
                              {dayEntries.length > 0 && (
                                <span className={cn(
                                  "text-[8px] data-mono mt-0.5",
                                  isToday ? "text-primary" : "text-muted-foreground/70"
                                )}>
                                  {dayEntries.length} run{dayEntries.length !== 1 ? "s" : ""}
                                </span>
                              )}
                            </div>

                            {/* Time slots */}
                            <div className="relative">
                              {/* Hour grid lines */}
                              {hours.map((h) => (
                                <div
                                  key={h}
                                  className="border-b opacity-50"
                                  style={{ height: HOUR_HEIGHT }}
                                />
                              ))}

                              {/* Current time indicator */}
                              {isToday && nowHour >= minHour && nowHour <= maxHour + 1 && (
                                <div
                                  className="absolute left-0 right-0 z-20 pointer-events-none"
                                  style={{ top: (nowHour - minHour) * HOUR_HEIGHT }}
                                >
                                  <div className="flex items-center">
                                    <div className="h-2.5 w-2.5 rounded-full -ml-[5px] shrink-0 bg-destructive" />
                                    <div className="flex-1 h-[2px] bg-destructive" />
                                  </div>
                                </div>
                              )}

                              {/* Event blocks */}
                              {dayEntries.map((entry, i) => {
                                const t = new Date(entry.time);
                                const entryHour = t.getHours() + t.getMinutes() / 60;
                                const top = (entryHour - minHour) * HOUR_HEIGHT;
                                const color = botColorMap[entry.bot_name] || "#58A6FF";
                                const isPast = t.getTime() < Date.now();
                                const diffMs = t.getTime() - Date.now();
                                const diffMins = Math.floor(diffMs / 60000);
                                const diffHrs = Math.floor(diffMins / 60);
                                const timeStr = t.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

                                // Stack overlapping events
                                const sameSlot = dayEntries.filter((e) => {
                                  const eH = new Date(e.time).getHours();
                                  return eH === t.getHours();
                                });
                                const slotIdx = sameSlot.indexOf(entry);
                                const slotCount = sameSlot.length;
                                const leftPct = slotCount > 1 ? (slotIdx / slotCount) * 100 : 0;
                                const widthPct = slotCount > 1 ? 100 / slotCount : 100;

                                return (
                                  <div
                                    key={i}
                                    className="absolute cursor-pointer transition-all group"
                                    style={{
                                      top: top + 2,
                                      left: `calc(${leftPct}% + 2px)`,
                                      width: `calc(${widthPct}% - 4px)`,
                                      opacity: isPast ? 0.35 : 1,
                                      zIndex: 10,
                                    }}
                                    onClick={() => { setShowCalendar(false); router.push(`/bots/${entry.bot_name}`); }}
                                  >
                                    <div
                                      className="rounded-md px-1.5 py-1 overflow-hidden transition-all group-hover:shadow-lg group-hover:scale-[1.02]"
                                      style={{
                                        background: `${color}18`,
                                        borderLeft: `3px solid ${color}`,
                                        minHeight: 28,
                                      }}
                                    >
                                      <p
                                        className="text-[9px] font-bold truncate leading-tight"
                                        style={{ color }}
                                      >
                                        {entry.display_name}
                                      </p>
                                      <p
                                        className="text-[8px] data-mono truncate leading-tight"
                                        style={{ color: `${color}99` }}
                                      >
                                        {timeStr}
                                        {!isPast && diffMins > 0 && (
                                          <span> &middot; {diffHrs > 0 ? `${diffHrs}h${diffMins % 60 > 0 ? ` ${diffMins % 60}m` : ""}` : `${diffMins}m`}</span>
                                        )}
                                      </p>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Footer with summary stats */}
            <div className="flex items-center justify-between px-6 py-3 border-t bg-muted/50">
              <div className="flex items-center gap-4">
                {(() => {
                  const statusCounts: Record<string, number> = {};
                  for (const e of calendarEntries) {
                    statusCounts[e.status] = (statusCounts[e.status] || 0) + 1;
                  }
                  return Object.entries(statusCounts).map(([status, count]) => (
                    <div key={status} className="flex items-center gap-1.5">
                      <span className={cn("h-2 w-2 rounded-full", {
                        "bg-success": status === "running",
                        "bg-primary": status === "scheduled",
                        "bg-warning": status === "paused",
                        "bg-destructive": status === "errored",
                        "bg-muted-foreground": !["running", "scheduled", "paused", "errored"].includes(status),
                      })} />
                      <span className={cn("text-[10px] font-medium", {
                        "text-success": status === "running",
                        "text-primary": status === "scheduled",
                        "text-warning": status === "paused",
                        "text-destructive": status === "errored",
                        "text-muted-foreground": !["running", "scheduled", "paused", "errored"].includes(status),
                      })}>
                        {count} {status}
                      </span>
                    </div>
                  ));
                })()}
              </div>
              <div className="flex items-center gap-3">
                {(() => {
                  const nextEntry = calendarEntries.find((e) => new Date(e.time).getTime() > Date.now());
                  if (!nextEntry) return null;
                  const diffMs = new Date(nextEntry.time).getTime() - Date.now();
                  const diffMins = Math.floor(diffMs / 60000);
                  const diffHrs = Math.floor(diffMins / 60);
                  return (
                    <span className="text-[10px] text-muted-foreground/70">
                      Next run: <span className="font-semibold text-primary">
                        {nextEntry.display_name}
                      </span> in {diffHrs > 0 ? `${diffHrs}h ${diffMins % 60}m` : `${diffMins}m`}
                    </span>
                  );
                })()}
                <span className="text-[10px] data-mono text-muted-foreground/70">
                  {calendarEntries.length} total runs
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
