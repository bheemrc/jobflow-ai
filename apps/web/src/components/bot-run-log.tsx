"use client";

import { useEffect, useRef } from "react";
import type { BotLogEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

const LEVEL_STYLES: Record<string, { colorClass: string; icon: string }> = {
  info: { colorClass: "text-primary bg-primary/10", icon: "i" },
  warning: { colorClass: "text-warning bg-warning/10", icon: "!" },
  error: { colorClass: "text-destructive bg-destructive/10", icon: "x" },
  debug: { colorClass: "text-muted-foreground bg-muted", icon: "d" },
};

interface BotRunLogProps {
  logs: BotLogEntry[];
  maxHeight?: number;
  autoScroll?: boolean;
}

export default function BotRunLog({ logs, maxHeight = 300, autoScroll = true }: BotRunLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  if (logs.length === 0) {
    return (
      <div className="rounded-lg p-4 text-center bg-card border">
        <p className="text-xs text-muted-foreground/70">
          No log entries yet.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="rounded-lg overflow-auto font-mono text-[11px] bg-background border"
      style={{ maxHeight }}
    >
      <div className="p-2 space-y-0.5">
        {logs.map((log, i) => {
          const style = LEVEL_STYLES[log.level] || LEVEL_STYLES.info;
          const time = new Date(log.created_at).toLocaleTimeString();
          return (
            <div
              key={log.id || i}
              className="flex gap-2 py-0.5 px-1 rounded hover:bg-accent"
            >
              <span
                className={cn("shrink-0 w-3 h-3 rounded-sm flex items-center justify-center text-[8px] font-bold mt-0.5", style.colorClass)}
              >
                {style.icon}
              </span>
              <span className="shrink-0 w-16 text-muted-foreground/70">
                {time}
              </span>
              <span className="shrink-0 w-20 truncate text-muted-foreground/70">
                {log.event_type}
              </span>
              <span className="text-muted-foreground">
                {log.message}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
