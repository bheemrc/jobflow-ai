"use client";

import { memo, useState } from "react";
import { AgentAvatar, getAgentConfig } from "./agent-avatar";
import { WorkspacePanel } from "./workspace-panel";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { GroupChat } from "@/lib/types";

interface ChatSidebarProps {
  chat: GroupChat;
  currentSpeaker: string | null;
}

function ChatSidebarComponent({ chat, currentSpeaker }: ChatSidebarProps) {
  const [activeView, setActiveView] = useState<"info" | "workspace">("workspace");
  const maxTurns = chat.config?.max_turns || chat.max_turns || 20;
  const maxTokens = chat.config?.max_tokens || chat.max_tokens || 50000;
  const turnsProgress = (chat.turns_used / maxTurns) * 100;
  const tokensProgress = (chat.tokens_used / maxTokens) * 100;

  return (
    <aside
      className="shrink-0 flex flex-col animate-slide-in-right overflow-hidden bg-card border-l w-[440px] min-w-[440px] max-w-[440px]"
    >
      {/* View Toggle */}
      <div className="shrink-0 p-3 flex gap-1 w-full border-b">
        <button
          onClick={() => setActiveView("workspace")}
          className={cn(
            "flex-1 py-1.5 px-3 rounded-lg text-[11px] font-semibold transition-colors",
            activeView === "workspace"
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          Workspace
        </button>
        <button
          onClick={() => setActiveView("info")}
          className={cn(
            "flex-1 py-1.5 px-3 rounded-lg text-[11px] font-semibold transition-colors",
            activeView === "info"
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          Info
        </button>
      </div>

      {/* Workspace View */}
      {activeView === "workspace" && (
        <div className="flex-1 overflow-hidden w-full max-w-full">
          <WorkspacePanel chatId={chat.id} isActive={chat.status === "active"} />
        </div>
      )}

      {/* Info View */}
      {activeView === "info" && (
        <div className="flex-1 overflow-y-auto">
          {/* Topic Section */}
          <div className="p-5 border-b">
        <h3 className="text-[11px] font-bold uppercase tracking-wider mb-2 text-muted-foreground">
          Topic
        </h3>
        <p className="text-[14px] font-medium leading-relaxed text-foreground">
          {chat.topic}
        </p>
      </div>

      {/* Status Section */}
      <div className="p-5 border-b">
        <h3 className="text-[11px] font-bold uppercase tracking-wider mb-3 text-muted-foreground">
          Status
        </h3>

        <div className="flex items-center gap-2 mb-4">
          <div
            className={cn(
              "h-2.5 w-2.5 rounded-full",
              chat.status === "active" && "animate-pulse"
            )}
            style={{
              background:
                chat.status === "active"
                  ? "hsl(var(--success))"
                  : chat.status === "paused"
                  ? "hsl(var(--warning))"
                  : "hsl(var(--muted-foreground))",
              boxShadow:
                chat.status === "active"
                  ? "0 0 8px hsl(var(--success))"
                  : "none",
            }}
          />
          <span
            className={cn(
              "text-[13px] font-semibold capitalize",
              chat.status === "active" && "text-success",
              chat.status === "paused" && "text-warning",
              chat.status === "concluded" && "text-muted-foreground"
            )}
          >
            {chat.status}
          </span>
        </div>

        {/* Progress meters */}
        <div className="space-y-4">
          {/* Turns */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-medium text-muted-foreground">
                Turns
              </span>
              <span className="text-[11px] data-mono text-muted-foreground">
                {chat.turns_used} / {maxTurns}
              </span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden bg-muted">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  turnsProgress > 80 ? "bg-warning" : "bg-primary"
                )}
                style={{ width: `${Math.min(turnsProgress, 100)}%` }}
              />
            </div>
          </div>

          {/* Tokens */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-medium text-muted-foreground">
                Tokens
              </span>
              <span className="text-[11px] data-mono text-muted-foreground">
                {(chat.tokens_used / 1000).toFixed(1)}k / {(maxTokens / 1000).toFixed(0)}k
              </span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden bg-muted">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  tokensProgress > 80 ? "bg-warning" : "bg-success"
                )}
                style={{ width: `${Math.min(tokensProgress, 100)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Participants Section */}
      <div className="p-5">
        <h3 className="text-[11px] font-bold uppercase tracking-wider mb-3 text-muted-foreground">
          Participants ({chat.participants.length})
        </h3>

        <div className="space-y-2">
          {chat.participants.map((agent) => {
            const config = getAgentConfig(agent);
            const isSpeaking = currentSpeaker === agent;

            return (
              <div
                key={agent}
                className={cn(
                  "flex items-center gap-3 p-2.5 rounded-xl transition-all duration-300 border",
                  isSpeaking ? "scale-[1.02] shadow-sm" : "bg-muted/50"
                )}
                style={{
                  background: isSpeaking
                    ? `linear-gradient(135deg, ${config.color}15, ${config.color}08)`
                    : undefined,
                  borderColor: isSpeaking
                    ? `${config.color}40`
                    : undefined,
                }}
              >
                <div className="relative">
                  <AgentAvatar agent={agent} size="sm" />
                  {isSpeaking && (
                    <div
                      className="absolute inset-0 rounded-lg animate-thinking-ring"
                      style={{ border: `2px solid ${config.color}` }}
                    />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className="text-[12px] font-semibold truncate"
                      style={{ color: config.color }}
                    >
                      {config.name}
                    </span>
                    {isSpeaking && (
                      <span
                        className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase animate-pulse"
                        style={{
                          background: `${config.color}25`,
                          color: config.color,
                        }}
                      >
                        Typing
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] truncate text-muted-foreground">
                    {config.description || config.role || "Agent"}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tools Section */}
      {chat.config?.allowed_tools && chat.config.allowed_tools.length > 0 && (
        <div className="p-5 border-t">
          <h3 className="text-[11px] font-bold uppercase tracking-wider mb-3 text-muted-foreground">
            Active Tools
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {chat.config.allowed_tools.map((tool) => (
              <Badge key={tool} variant="secondary" className="text-[10px]">
                {tool.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Meta Info */}
      <div className="p-5 border-t">
        <div className="space-y-2 text-[11px] text-muted-foreground">
          <div className="flex items-center justify-between">
            <span>Started</span>
            <span className="data-mono text-muted-foreground">
              {new Date(chat.created_at).toLocaleTimeString(undefined, {
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>Turn Mode</span>
            <span className="text-muted-foreground">
              {chat.config?.turn_mode || "mention_driven"}
            </span>
          </div>
        </div>
      </div>
        </div>
      )}
    </aside>
  );
}

export const ChatSidebar = memo(ChatSidebarComponent);
