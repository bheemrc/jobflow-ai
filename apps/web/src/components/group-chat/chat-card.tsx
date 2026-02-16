"use client";

import { memo } from "react";
import Link from "next/link";
import { AgentAvatar, getAgentConfig } from "./agent-avatar";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { GroupChat } from "@/lib/types";

interface ChatCardProps {
  chat: GroupChat;
}

function ChatCardComponent({ chat }: ChatCardProps) {
  const maxTurns = chat.config?.max_turns || chat.max_turns || 20;
  const turnPercentage = (chat.turns_used / maxTurns) * 100;

  const getStatusBadge = () => {
    switch (chat.status) {
      case "active":
        return { variant: "success" as const, label: "Live", showDot: true };
      case "paused":
        return { variant: "warning" as const, label: "Paused", showDot: false };
      case "concluded":
        return { variant: "secondary" as const, label: "Concluded", showDot: false };
      default:
        return { variant: "secondary" as const, label: chat.status, showDot: false };
    }
  };

  const status = getStatusBadge();

  // Get last 2 speakers for activity preview
  const recentAgents = chat.participants.slice(0, 2);

  return (
    <Link href={`/group-chats/${chat.id}`}>
      <Card
        className={cn(
          "p-5 cursor-pointer group relative overflow-hidden hover:shadow-md transition-all",
          chat.status === "active" && "ring-1 ring-success/30"
        )}
      >
        {/* Active glow border */}
        {chat.status === "active" && (
          <div className="absolute inset-0 rounded-[14px] pointer-events-none animate-pulse border border-success/30" />
        )}

        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            {/* Status + ID row */}
            <div className="flex items-center gap-2 mb-2">
              <Badge
                variant={status.variant}
                className={cn("text-[10px] uppercase", chat.status === "active" && "animate-pulse")}
              >
                {status.showDot && (
                  <span className="h-1.5 w-1.5 rounded-full bg-current mr-1" />
                )}
                {status.label}
              </Badge>
              <span className="data-mono text-[10px] text-muted-foreground">
                #{chat.id}
              </span>
            </div>

            {/* Topic */}
            <h3 className="text-[15px] font-semibold leading-snug line-clamp-2 text-foreground group-hover:text-primary transition-colors">
              {chat.topic}
            </h3>
          </div>

          {/* Participants avatars - stacked with overlap */}
          <div className="flex -space-x-2 shrink-0">
            {chat.participants.slice(0, 4).map((agent, i) => (
              <div
                key={agent}
                className="transition-transform group-hover:translate-x-0"
                style={{
                  transform: `translateX(${i * 4}px)`,
                  zIndex: chat.participants.length - i,
                }}
              >
                <AgentAvatar agent={agent} size="sm" />
              </div>
            ))}
            {chat.participants.length > 4 && (
              <div
                className="h-6 w-6 rounded-xl flex items-center justify-center text-[9px] font-bold relative bg-muted border-2 border-card text-muted-foreground"
                style={{ zIndex: 0 }}
              >
                +{chat.participants.length - 4}
              </div>
            )}
          </div>
        </div>

        {/* Progress section */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-medium text-muted-foreground">
              Progress
            </span>
            <span className="data-mono text-[10px] text-muted-foreground">
              {chat.turns_used}/{maxTurns} turns
            </span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                chat.status === "concluded"
                  ? "bg-muted-foreground"
                  : turnPercentage > 80
                  ? "bg-warning"
                  : "bg-primary"
              )}
              style={{
                width: `${Math.min(turnPercentage, 100)}%`,
              }}
            />
          </div>
        </div>

        {/* Active chat: show who's talking */}
        {chat.status === "active" && recentAgents.length > 0 && (
          <div className="flex items-center gap-2 mb-3 p-2 rounded-lg bg-card border">
            <div className="flex -space-x-1">
              {recentAgents.map((agent) => (
                <AgentAvatar key={agent} agent={agent} size="xs" />
              ))}
            </div>
            <span className="text-[11px] text-muted-foreground">
              <span style={{ color: getAgentConfig(recentAgents[0]).color }}>
                {getAgentConfig(recentAgents[0]).name}
              </span>
              {recentAgents.length > 1 && (
                <>
                  {" and "}
                  <span style={{ color: getAgentConfig(recentAgents[1]).color }}>
                    {getAgentConfig(recentAgents[1]).name}
                  </span>
                </>
              )} are discussing...
            </span>
          </div>
        )}

        {/* Stats row */}
        <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {chat.participants.length} agents
          </span>
          <span className="flex items-center gap-1.5">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {formatDate(chat.created_at)}
          </span>

          {/* Tools indicator */}
          {chat.config?.allowed_tools && chat.config.allowed_tools.length > 0 && (
            <span className="flex items-center gap-1.5 ml-auto">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
              </svg>
              {chat.config.allowed_tools.length}
            </span>
          )}
        </div>

        {/* Summary preview for concluded chats */}
        {chat.status === "concluded" && chat.summary && (
          <div className="mt-3 pt-3 border-t">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-sm">{"\uD83E\uDDEC"}</span>
              <span className="text-[10px] font-bold uppercase text-purple-400">
                Synthesis
              </span>
            </div>
            <p className="text-[12px] leading-relaxed line-clamp-2 text-muted-foreground">
              {chat.summary}
            </p>
          </div>
        )}
      </Card>
    </Link>
  );
}

export const ChatCard = memo(ChatCardComponent);

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
