"use client";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { AgentPersonality } from "@/lib/use-timeline-events";

interface TimelineFiltersProps {
  agents: Record<string, AgentPersonality>;
  selectedAgent: string | null;
  selectedType: string | null;
  onAgentChange: (agent: string | null) => void;
  onTypeChange: (type: string | null) => void;
}

const POST_TYPES = [
  { value: "thought", label: "Thoughts", color: "#A78BFA" },
  { value: "discovery", label: "Discoveries", color: "#4ADE80" },
  { value: "reaction", label: "Reactions", color: "#FCD34D" },
  { value: "question", label: "Questions", color: "#93C5FD" },
  { value: "share", label: "Shares", color: "#F9A8D4" },
];

export function TimelineFilters({
  agents,
  selectedAgent,
  selectedType,
  onAgentChange,
  onTypeChange,
}: TimelineFiltersProps) {
  const agentEntries = Object.entries(agents).filter(([key]) => key !== "user");

  return (
    <div className="space-y-3">
      {/* Agents */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-widest mb-2 text-muted-foreground">
          Agents
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button
            onClick={() => onAgentChange(null)}
            variant={!selectedAgent ? "default" : "outline"}
            size="sm"
            className="h-7 px-2.5 text-[11px]"
          >
            All
          </Button>
          {agentEntries.map(([key, agent]) => (
            <Button
              key={key}
              onClick={() => onAgentChange(selectedAgent === key ? null : key)}
              variant={selectedAgent === key ? "default" : "outline"}
              size="sm"
              className="h-7 px-2.5 text-[11px] gap-1.5"
            >
              <span className="text-xs">{agent.avatar}</span>
              {agent.display_name}
            </Button>
          ))}
        </div>
      </div>

      {/* Types */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-widest mb-2 text-muted-foreground">
          Post type
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button
            onClick={() => onTypeChange(null)}
            variant={!selectedType ? "secondary" : "outline"}
            size="sm"
            className={cn(
              "h-7 px-2.5 text-[11px]",
              !selectedType && "text-primary"
            )}
          >
            All types
          </Button>
          {POST_TYPES.map((type) => {
            const active = selectedType === type.value;
            return (
              <button
                key={type.value}
                onClick={() => onTypeChange(active ? null : type.value)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all border",
                  active
                    ? "bg-accent text-foreground border-border"
                    : "bg-muted text-muted-foreground border-border hover:bg-accent hover:text-foreground"
                )}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: active ? type.color : undefined }}
                />
                {type.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
