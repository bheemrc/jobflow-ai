"use client";

import { memo } from "react";
import { AgentAvatar, getAgentConfig } from "./agent-avatar";
import { Badge } from "@/components/ui/badge";

interface TypingIndicatorProps {
  agent: string;
  turn: number;
}

function TypingIndicatorComponent({ agent, turn }: TypingIndicatorProps) {
  const config = getAgentConfig(agent);

  return (
    <div className="animate-slide-in-message">
      <div
        className="flex gap-3 p-4 rounded-2xl bg-muted/30 border"
        style={{
          borderColor: `${config.color}30`,
        }}
      >
        {/* Pulsing avatar */}
        <div className="relative shrink-0">
          <AgentAvatar agent={agent} size="md" />
          {/* Thinking ring animation */}
          <div
            className="absolute inset-0 rounded-xl animate-thinking-ring opacity-60"
            style={{
              border: `2px solid ${config.color}`,
            }}
          />
        </div>

        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-2">
            <span
              className="font-bold text-[14px]"
              style={{ color: config.color }}
            >
              {config.name}
            </span>
            <span
              className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
              style={{
                background: `${config.color}20`,
                color: config.color,
              }}
            >
              Thinking...
            </span>
            <Badge variant="secondary" className="text-[10px] font-mono px-1.5 py-0.5">
              Turn #{turn}
            </Badge>
          </div>

          {/* Animated typing dots */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-2 w-2 rounded-full animate-typing-dot"
                  style={{
                    background: config.color,
                    animationDelay: `${i * 0.15}s`,
                  }}
                />
              ))}
            </div>
            <span className="text-[12px] italic text-muted-foreground">
              formulating response...
            </span>
          </div>

          {/* Progress bar */}
          <div className="mt-3 h-1 rounded-full overflow-hidden bg-muted">
            <div
              className="h-full rounded-full animate-typing-progress"
              style={{ background: config.color }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export const TypingIndicator = memo(TypingIndicatorComponent);
