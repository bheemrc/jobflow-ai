"use client";

import type { BotState } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<string, { label: string; pulse?: boolean; badgeVariant: "success" | "info" | "warning" | "secondary" | "destructive" }> = {
  running: { label: "Running", pulse: true, badgeVariant: "success" },
  waiting: { label: "Waiting for events", badgeVariant: "info" },
  scheduled: { label: "Waiting for events", badgeVariant: "info" },
  paused: { label: "Paused", badgeVariant: "warning" },
  stopped: { label: "Stopped", badgeVariant: "secondary" },
  errored: { label: "Error", badgeVariant: "destructive" },
  disabled: { label: "Disabled", badgeVariant: "secondary" },
};

interface BotCardProps {
  bot: BotState;
  onStart: () => void;
  onStop: () => void;
  onPause: () => void;
  onResume: () => void;
  onToggleEnabled?: (enabled: boolean) => void;
  onClick: () => void;
}

export default function BotCard({ bot, onStart, onStop, onPause, onResume, onToggleEnabled, onClick }: BotCardProps) {
  const status = STATUS_CONFIG[bot.status] || STATUS_CONFIG.stopped;

  const formatTime = (iso: string | null) => {
    if (!iso) return "Never";
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  };

  const scheduleLabel = () => {
    const s = bot.config.schedule;
    if (!s) return "";
    if (s.type === "interval") return `Every ${s.hours || 0}h`;
    if (s.type === "cron") return `Daily at ${String(s.hour ?? 0).padStart(2, "0")}:${String(s.minute ?? 0).padStart(2, "0")}`;
    return "";
  };

  return (
    <Card
      className="cursor-pointer p-4 min-h-[180px] hover:shadow-md hover:border-primary/20 transition-all"
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold truncate text-foreground">
            {bot.display_name}
          </h3>
          <p className="text-[11px] mt-0.5 line-clamp-2 text-muted-foreground/70">
            {bot.description}
          </p>
        </div>
        <div className="flex items-center gap-1.5 ml-2 shrink-0">
          {status.pulse && (
            <span className="h-2 w-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_hsl(var(--success))]" />
          )}
          {!status.pulse && (
            <span className={cn("h-2 w-2 rounded-full", {
              "bg-success": bot.status === "running",
              "bg-primary": bot.status === "waiting" || bot.status === "scheduled",
              "bg-warning": bot.status === "paused",
              "bg-muted-foreground": bot.status === "stopped" || bot.status === "disabled",
              "bg-destructive": bot.status === "errored",
            })} />
          )}
          {bot.is_custom && (
            <Badge variant="secondary" className="bg-purple-500/15 text-purple-500 border-0">
              Custom
            </Badge>
          )}
          <Badge variant={status.badgeVariant}>
            {status.label}
          </Badge>
          {onToggleEnabled && (
            <Switch
              checked={bot.enabled}
              onCheckedChange={(checked) => { onToggleEnabled(checked); }}
              onClick={(e) => e.stopPropagation()}
              className="h-4 w-7 data-[state=checked]:bg-primary data-[state=unchecked]:bg-muted [&>span]:h-3 [&>span]:w-3 [&>span]:data-[state=checked]:translate-x-3"
              title={bot.enabled ? "Disable bot" : "Enable bot"}
            />
          )}
        </div>
      </div>

      {/* Integration badges */}
      {bot.integrations && Object.keys(bot.integrations).length > 0 && (
        <div className="flex gap-1 mb-2">
          {Object.keys(bot.integrations).map((key) => (
            <Badge key={key} variant="secondary" className="text-[8px] font-semibold uppercase bg-pink-500/15 text-pink-400 border-0 px-1.5 py-0.5">
              {key}
            </Badge>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 mb-2">
        <div>
          <p className="text-[9px] uppercase tracking-wider mb-0.5 text-muted-foreground/70">Last Run</p>
          <p className="data-mono text-xs text-muted-foreground">
            {formatTime(bot.last_run_at)}
          </p>
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-wider mb-0.5 text-muted-foreground/70">Schedule</p>
          <p className="data-mono text-xs text-muted-foreground">
            {scheduleLabel()}
          </p>
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-wider mb-0.5 text-muted-foreground/70">Runs</p>
          <p className="data-mono text-xs flex items-center gap-1.5 text-muted-foreground">
            {bot.total_runs}
            {bot.last_run_cost != null && bot.last_run_cost > 0 && (
              <span className="text-[9px] text-primary">
                ${bot.last_run_cost.toFixed(4)}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Last run output preview */}
      {bot.last_output_preview && (
        <div
          className={cn(
            "rounded-lg px-2.5 py-2 mb-2 text-[10px] leading-snug line-clamp-2 overflow-hidden bg-card border text-muted-foreground/70",
            bot.last_run_status === "errored" && "border-destructive/30"
          )}
        >
          {bot.last_output_preview.slice(0, 150)}
        </div>
      )}

      <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
        {bot.status === "running" ? (
          <Button
            onClick={onStop}
            variant="ghost"
            className="flex-1 py-1.5 h-auto text-[11px] font-medium bg-destructive/10 text-destructive hover:bg-destructive/20"
          >
            Stop
          </Button>
        ) : bot.status === "paused" ? (
          <Button
            onClick={onResume}
            variant="ghost"
            className="flex-1 py-1.5 h-auto text-[11px] font-medium bg-primary/10 text-primary hover:bg-primary/20"
          >
            Resume
          </Button>
        ) : (
          <Button
            onClick={onStart}
            variant="ghost"
            className="flex-1 py-1.5 h-auto text-[11px] font-medium bg-success/10 text-success hover:bg-success/20"
          >
            Start
          </Button>
        )}
        {bot.status === "running" || bot.status === "waiting" || bot.status === "scheduled" ? (
          <Button
            onClick={onPause}
            variant="ghost"
            className="px-3 py-1.5 h-auto text-[11px] font-medium bg-muted text-muted-foreground hover:bg-accent"
          >
            Pause
          </Button>
        ) : null}
        {bot.config.requires_approval && (
          <Badge variant="warning" className="flex items-center px-2 rounded-lg text-[9px] font-semibold uppercase">
            Approval
          </Badge>
        )}
      </div>
    </Card>
  );
}
