"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import type { AgentPersonality } from "@/lib/use-timeline-events";
import type { AgentMemory } from "@/lib/agent-memory";

interface AgentProfileProps {
  agentKey: string;
  displayName: string;
  avatar: string;
  color: string;
  bio: string;
  role: string;
  isDynamic: boolean;
  reputation?: number;
  postCount?: number;
  memory?: AgentMemory;
  children: React.ReactNode;
}

export function AgentProfile({
  agentKey,
  displayName,
  avatar,
  color,
  bio,
  role,
  isDynamic,
  reputation,
  postCount,
  memory,
  children,
}: AgentProfileProps) {
  const [showProfile, setShowProfile] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseEnter = () => {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setShowProfile(true), 400);
  };

  const handleMouseLeave = () => {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setShowProfile(false), 200);
  };

  useEffect(() => {
    return () => clearTimeout(timeoutRef.current);
  }, []);

  const repScore = reputation ?? 0;
  const repLabel = repScore > 10 ? "Legendary" : repScore > 5 ? "Trusted" : repScore > 0 ? "Rising" : "New";
  const repColor = repScore > 10 ? "#FBBF24" : repScore > 5 ? "#4ADE80" : repScore > 0 ? "#58A6FF" : undefined;

  return (
    <div
      ref={containerRef}
      className="relative inline-flex"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}

      {showProfile && (
        <div
          className="absolute z-50 top-full left-0 mt-2 w-[240px] rounded-xl p-3 animate-fade-in bg-popover border shadow-xl backdrop-blur-xl"
          style={{
            borderColor: `${color}25`,
          }}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          {/* Header */}
          <div className="flex items-center gap-2.5 mb-2.5">
            <div
              className="h-10 w-10 rounded-xl flex items-center justify-center text-lg"
              style={{
                background: `${color}15`,
                border: `1.5px solid ${color}30`,
              }}
            >
              {avatar}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-[13px] font-bold truncate" style={{ color }}>
                  {displayName}
                </span>
                {isDynamic && (
                  <span className="text-[7px] font-bold px-1 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
                    DYN
                  </span>
                )}
              </div>
              {role && (
                <div className="text-[10px] text-muted-foreground">
                  {role}
                </div>
              )}
            </div>
          </div>

          {/* Bio */}
          {bio && (
            <p className="text-[10px] leading-relaxed mb-2.5 text-muted-foreground">
              {bio}
            </p>
          )}

          {/* Stats row */}
          <div className="flex items-center gap-3 py-2 px-2 rounded-lg mb-2 bg-muted">
            <div className="text-center flex-1">
              <div className="text-[12px] font-bold data-mono text-foreground">
                {repScore}
              </div>
              <div className="text-[8px] uppercase tracking-wider text-muted-foreground">
                Rep
              </div>
            </div>
            <Separator orientation="vertical" className="h-6" />
            <div className="text-center flex-1">
              <div className="text-[12px] font-bold data-mono text-foreground">
                {postCount ?? "\u2014"}
              </div>
              <div className="text-[8px] uppercase tracking-wider text-muted-foreground">
                Signals
              </div>
            </div>
            <Separator orientation="vertical" className="h-6" />
            <div className="text-center flex-1">
              <div
                className={cn("text-[10px] font-bold", !repColor && "text-muted-foreground")}
                style={repColor ? { color: repColor } : undefined}
              >
                {repLabel}
              </div>
              <div className="text-[8px] uppercase tracking-wider text-muted-foreground">
                Rank
              </div>
            </div>
          </div>

          {/* Memory / Context */}
          {memory && memory.topTopics.length > 0 && (
            <div className="mb-2">
              <div className="flex items-center gap-1 mb-1.5">
                <span className="text-[8px] font-bold uppercase tracking-wider text-muted-foreground">
                  &#x1F9E0; Memory
                </span>
                {memory.recentInteractions > 0 && (
                  <span className="text-[7px] font-bold px-1 py-0.5 rounded bg-green-400/10 text-green-400">
                    Active
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1">
                {memory.topTopics.slice(0, 4).map((topic) => (
                  <span
                    key={topic}
                    className="text-[8px] px-1.5 py-0.5 rounded-full"
                    style={{
                      background: `${color}10`,
                      color: `${color}CC`,
                      border: `1px solid ${color}15`,
                    }}
                  >
                    {topic}
                  </span>
                ))}
              </div>
              {memory.interactedWith.length > 0 && (
                <div className="mt-1.5 text-[8px] text-muted-foreground">
                  Collaborates with {memory.interactedWith.slice(0, 3).join(", ")}
                  {memory.interactedWith.length > 3 && ` +${memory.interactedWith.length - 3}`}
                </div>
              )}
              {/* Top realm */}
              {Object.keys(memory.realms).length > 0 && (
                <div className="mt-1 text-[8px] text-muted-foreground">
                  Most active in{" "}
                  <span style={{ color }}>
                    {Object.entries(memory.realms).sort((a, b) => b[1] - a[1])[0][0]}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Agent ID */}
          <div className="flex items-center gap-1.5">
            <span className="text-[8px] data-mono text-muted-foreground">
              ID: {agentKey}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
