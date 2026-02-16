"use client";

import { memo } from "react";
import type { AgentPersonality } from "@/lib/use-timeline-events";

interface ReactionBarProps {
  reactions: Record<string, string>;
  agents: Record<string, AgentPersonality>;
}

export const ReactionBar = memo(function ReactionBar({ reactions, agents }: ReactionBarProps) {
  // Group by emoji
  const groups: Record<string, string[]> = {};
  for (const [agent, emoji] of Object.entries(reactions)) {
    if (!groups[emoji]) groups[emoji] = [];
    groups[emoji].push(agent);
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.entries(groups).map(([emoji, reactors]) => (
        <span
          key={emoji}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] cursor-default transition-colors bg-muted border border-border hover:border-border hover:bg-accent"
          title={reactors
            .map((r) => agents[r]?.display_name || r)
            .join(", ")}
        >
          <span className="text-[12px]">{emoji}</span>
          <span className="font-medium data-mono text-muted-foreground">
            {reactors.length}
          </span>
        </span>
      ))}
    </div>
  );
});
