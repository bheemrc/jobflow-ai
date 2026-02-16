"use client";

import { memo } from "react";
import type { KatalystEvent } from "@/lib/use-katalyst-events";

const EVENT_ICONS: Record<string, { icon: string; color: string }> = {
  reaction_spawned: { icon: "⚡", color: "#58A6FF" },
  reaction_completed: { icon: "✓", color: "#56D364" },
  workstream_started: { icon: "▶", color: "#58A6FF" },
  workstream_advanced: { icon: "→", color: "#A78BFA" },
  workstream_review: { icon: "◉", color: "#F97316" },
  artifact_created: { icon: "◆", color: "#22D3EE" },
  artifact_updated: { icon: "◇", color: "#22D3EE" },
  blocker_created: { icon: "⬡", color: "#E3B341" },
  blocker_resolved: { icon: "✓", color: "#56D364" },
  blocker_auto_resolved: { icon: "✦", color: "#56D364" },
};

function getEventStyle(eventType: string) {
  return EVENT_ICONS[eventType] || { icon: "·", color: "hsl(var(--muted-foreground))" };
}

function formatRelative(dateStr: string): string {
  const ms = Date.now() - new Date(dateStr).getTime();
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export const EventFeed = memo(function EventFeed({
  events,
}: {
  events: KatalystEvent[];
}) {
  if (events.length === 0) {
    return (
      <div className="rounded-xl p-6 text-center text-[12px] bg-card text-muted-foreground">
        No events yet
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      {events.map((event) => {
        const { icon, color } = getEventStyle(event.event_type);
        return (
          <div
            key={event.id}
            className="flex items-start gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-muted/50"
          >
            <span className="mt-0.5 text-[14px] leading-none" style={{ color }}>
              {icon}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] leading-snug text-muted-foreground">
                {event.message}
              </p>
              <div className="flex items-center gap-2 mt-0.5 text-[10px] text-muted-foreground">
                <span>{event.agent}</span>
                <span>·</span>
                <span>{formatRelative(event.created_at)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
});
