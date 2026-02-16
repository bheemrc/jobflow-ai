"use client";

import { memo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { AgentAvatar, getAgentConfig } from "./agent-avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { GroupChatMessage } from "@/lib/types";

interface MessageBubbleProps {
  message: GroupChatMessage;
  isLatest?: boolean;
  showThread?: boolean;
}

function MessageBubbleComponent({ message, isLatest = false, showThread = false }: MessageBubbleProps) {
  const config = getAgentConfig(message.agent);
  const timeAgo = formatTimeAgo(message.created_at);
  const [isExpanded, setIsExpanded] = useState(false);

  // Detect if content is long
  const isLongContent = message.content.length > 400;
  const displayContent = isLongContent && !isExpanded
    ? message.content.slice(0, 400) + "..."
    : message.content;

  // Highlight @mentions and workspace references in content
  const highlightMentions = (content: string) => {
    // Match @mentions, finding_N, task_N, decision_N
    const parts = content.split(/(@\w+|(?:finding|task|decision)_\d+)/gi);
    return parts.map((part, i) => {
      if (part.startsWith("@")) {
        const mentionAgent = part.slice(1).toLowerCase();
        const mentionConfig = getAgentConfig(mentionAgent);
        return (
          <span
            key={i}
            className="inline-flex items-center font-semibold px-1.5 py-0.5 rounded-md transition-all hover:scale-105 cursor-pointer"
            style={{
              color: mentionConfig.color,
              background: `${mentionConfig.color}15`,
              boxShadow: `0 0 0 1px ${mentionConfig.color}30`,
            }}
          >
            {part}
          </span>
        );
      }
      // Workspace references (finding_1, task_2, decision_1)
      const workspaceMatch = part.match(/^(finding|task|decision)_(\d+)$/i);
      if (workspaceMatch) {
        const type = workspaceMatch[1].toLowerCase();
        const colorMap: Record<string, string> = {
          finding: "text-primary",
          task: "text-warning",
          decision: "text-success",
        };
        const bgMap: Record<string, string> = {
          finding: "bg-primary/10",
          task: "bg-warning/10",
          decision: "bg-success/10",
        };
        return (
          <span
            key={i}
            className={cn(
              "inline-flex items-center gap-1 font-mono text-[12px] font-semibold px-1.5 py-0.5 rounded-md transition-all hover:scale-105 cursor-pointer",
              colorMap[type],
              bgMap[type]
            )}
            title={`View ${type} in workspace`}
          >
            {type === "finding" && (
              <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            )}
            {type === "task" && (
              <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            )}
            {type === "decision" && (
              <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            {part}
          </span>
        );
      }
      return part;
    });
  };

  // Process children from ReactMarkdown to highlight @mentions
  const processChildren = (children: React.ReactNode): React.ReactNode => {
    if (typeof children === "string") {
      return highlightMentions(children);
    }
    if (Array.isArray(children)) {
      return children.map((child, i) => {
        if (typeof child === "string") {
          return <span key={i}>{highlightMentions(child)}</span>;
        }
        return child;
      });
    }
    return children;
  };

  // Detect tool usage in content
  const hasToolUsage = message.content.includes("\uD83D\uDD0D") ||
                       message.content.includes("searching") ||
                       message.content.includes("found");

  return (
    <article
      className={cn(
        "chat-message group relative",
        showThread && "pl-8 border-l-2",
        isLatest && "animate-slide-in-message"
      )}
      style={{
        borderLeftColor: showThread ? `${config.color}40` : "transparent",
      }}
    >
      {/* Thread connector dot */}
      {showThread && (
        <div
          className="absolute left-[-5px] top-5 h-2 w-2 rounded-full"
          style={{ background: config.color }}
        />
      )}

      <div
        className={cn(
          "flex gap-3 p-4 rounded-2xl transition-all duration-300 border bg-muted/50 hover:shadow-lg",
          isLatest && "ring-2 ring-opacity-50"
        )}
        style={{
          "--tw-ring-color": isLatest ? config.color : "transparent",
        } as React.CSSProperties}
      >
        {/* Avatar with online indicator */}
        <div className="relative shrink-0">
          <AgentAvatar agent={message.agent} size="md" />
          <div
            className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-card"
            style={{
              background: config.color,
            }}
          />
        </div>

        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-2">
            <span
              className="font-bold text-[14px] hover:underline cursor-pointer"
              style={{ color: config.color }}
            >
              {config.name}
            </span>

            {/* Role badge */}
            <span
              className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
              style={{
                background: `${config.color}15`,
                color: config.color,
              }}
            >
              {config.role || "Agent"}
            </span>

            {/* Turn indicator */}
            <Badge variant="secondary" className="text-[10px] font-mono px-1.5 py-0.5">
              #{message.turn_number}
            </Badge>

            {/* Tool usage indicator */}
            {hasToolUsage && (
              <Badge variant="info" className="text-[10px] gap-1">
                <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Researched
              </Badge>
            )}

            <span className="text-[11px] ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground">
              {timeAgo}
            </span>
          </div>

          {/* Content with Markdown rendering */}
          <div className="prose text-[14px] text-foreground">
            <ReactMarkdown
              components={{
                // Custom paragraph to highlight @mentions
                p: ({ children }) => (
                  <p className="mb-3 last:mb-0">
                    {processChildren(children)}
                  </p>
                ),
                // Custom list item
                li: ({ children }) => (
                  <li className="mb-1">
                    {processChildren(children)}
                  </li>
                ),
                // Style bold text
                strong: ({ children }) => (
                  <strong className="font-semibold text-foreground">
                    {children}
                  </strong>
                ),
                // Style links
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:no-underline text-primary"
                  >
                    {children}
                  </a>
                ),
                // Style code
                code: ({ children }) => (
                  <code className="px-1.5 py-0.5 rounded text-[13px] bg-muted text-foreground">
                    {children}
                  </code>
                ),
                // Style headers
                h1: ({ children }) => <h1 className="text-lg font-bold mb-2 mt-4 first:mt-0">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-bold mb-1 mt-2 first:mt-0">{children}</h3>,
                // Style lists
                ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
              }}
            >
              {displayContent}
            </ReactMarkdown>
          </div>

          {/* Read more button */}
          {isLongContent && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-2 text-[12px] font-medium text-primary transition-colors hover:underline"
            >
              {isExpanded ? "Show less" : "Read more"}
            </button>
          )}

          {/* Mentions footer */}
          {message.mentions.length > 0 && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t">
              <svg
                className="h-3.5 w-3.5 text-muted-foreground"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
              </svg>
              <div className="flex items-center gap-1">
                {message.mentions.map((mention, idx) => {
                  const mentionConfig = getAgentConfig(mention);
                  return (
                    <span
                      key={`${mention}-${idx}`}
                      className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full transition-transform hover:scale-105"
                      style={{
                        background: `${mentionConfig.color}15`,
                        color: mentionConfig.color,
                      }}
                    >
                      <AgentAvatar agent={mention} size="xs" />
                      {mentionConfig.name}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* Action bar - visible on hover */}
          <div className="flex items-center gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] text-muted-foreground hover:text-foreground">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
              </svg>
              Share
            </Button>
            <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] text-muted-foreground hover:text-foreground">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              Save
            </Button>
            <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] text-muted-foreground hover:text-foreground">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
              </svg>
              More
            </Button>
          </div>
        </div>
      </div>
    </article>
  );
}

// Memoize to prevent re-renders
export const MessageBubble = memo(MessageBubbleComponent);

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);

  if (diffSec < 10) return "just now";
  if (diffSec < 60) return `${diffSec}s`;
  if (diffMin < 60) return `${diffMin}m`;
  if (diffHour < 24) return `${diffHour}h`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
