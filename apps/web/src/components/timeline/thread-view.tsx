"use client";

import { useState, useEffect, useCallback, memo, useRef } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { TimelinePost, AgentPersonality } from "@/lib/use-timeline-events";
import { resolveAgent } from "@/lib/use-timeline-events";
import Markdown from "@/components/markdown";

interface ThreadViewProps {
  postId: number;
  replyCount: number;
  agents: Record<string, AgentPersonality>;
  onReply?: (postId: number, content: string) => void;
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const then = new Date(dateStr);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  return `${Math.floor(diffHr / 24)}d`;
}

// Convergence phase badges
const PHASE_STYLES: Record<string, { label: string; color: string; icon: string }> = {
  research: { label: "Research", color: "#58A6FF", icon: "\u25C8" },
  debate: { label: "Debate", color: "#F97316", icon: "\u26A1" },
  synthesis: { label: "Synthesis", color: "#A78BFA", icon: "\u2B21" },
};

const INITIAL_VISIBLE = 3;
const THREAD_EST_HEIGHT = 140;
const THREAD_OVERSCAN = 4;

// Client-side cache for thread replies (stale-while-revalidate)
const replyCache = new Map<number, { replies: TimelinePost[]; count: number; ts: number }>();
const CACHE_TTL = 30_000; // 30 seconds

export const ThreadView = memo(function ThreadView({ postId, replyCount, agents, onReply }: ThreadViewProps) {
  const cached = replyCache.get(postId);
  const [replies, setReplies] = useState<TimelinePost[]>(cached?.replies || []);
  const [loading, setLoading] = useState(!cached);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [showAll, setShowAll] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);
  const [scrollY, setScrollY] = useState(0);
  const [viewportH, setViewportH] = useState(0);
  const [threadTop, setThreadTop] = useState(0);

  const fetchReplies = useCallback(() => {
    // Skip fetch if cache is fresh and count matches
    const entry = replyCache.get(postId);
    if (entry && entry.count === replyCount && Date.now() - entry.ts < CACHE_TTL) {
      setReplies(entry.replies);
      setLoading(false);
      return;
    }

    fetch(`/api/ai/timeline/${postId}`)
      .then((r) => r.json())
      .then((data) => {
        if (data?.replies) {
          setReplies(data.replies);
          replyCache.set(postId, { replies: data.replies, count: data.replies.length, ts: Date.now() });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [postId, replyCount]);

  useEffect(() => {
    fetchReplies();
  }, [fetchReplies]);

  useEffect(() => {
    if (!loading && replyCount > replies.length) {
      fetchReplies();
    }
  }, [replyCount, loading, replies.length, fetchReplies]);

  useEffect(() => {
    if (!showAll || replies.length <= 12) return;
    const updateScroll = () => {
      setScrollY(window.scrollY || 0);
      setViewportH(window.innerHeight || 0);
    };
    updateScroll();
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        updateScroll();
        ticking = false;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", updateScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", updateScroll);
    };
  }, [showAll, replies.length]);

  useEffect(() => {
    if (!showAll || replies.length <= 12 || !threadRef.current) return;
    const rect = threadRef.current.getBoundingClientRect();
    setThreadTop(rect.top + window.scrollY);
  }, [showAll, replies.length]);

  const toggleCollapse = (id: number) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="ml-4 pl-4 py-3 border-l-2 border-border">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {[0, 150, 300].map((delay) => (
              <span
                key={delay}
                className="block h-1.5 w-1.5 rounded-full animate-bounce bg-primary opacity-50"
                style={{
                  animationDelay: `${delay}ms`,
                  animationDuration: "0.8s",
                }}
              />
            ))}
          </div>
          <span className="text-[11px] text-muted-foreground">
            Loading convergence thread
          </span>
        </div>
      </div>
    );
  }

  if (replies.length === 0) {
    return (
      <div className="ml-4 pl-4 py-3 border-l-2 border-border">
        <p className="text-[11px] text-muted-foreground">
          No replies yet
        </p>
      </div>
    );
  }

  // Group replies by convergence phase for visual separation
  let currentPhase = "";
  const hiddenCount = !showAll && replies.length > INITIAL_VISIBLE ? replies.length - INITIAL_VISIBLE : 0;
  let visibleReplies = showAll ? replies : replies.slice(0, INITIAL_VISIBLE);
  let topSpacer = 0;
  let bottomSpacer = 0;
  if (showAll && replies.length > 12) {
    const total = replies.length;
    const start = Math.max(0, Math.floor((scrollY - threadTop) / THREAD_EST_HEIGHT) - THREAD_OVERSCAN);
    const count = Math.ceil(viewportH / THREAD_EST_HEIGHT) + THREAD_OVERSCAN * 2;
    const end = Math.min(total, start + count);
    visibleReplies = replies.slice(start, end);
    topSpacer = start * THREAD_EST_HEIGHT;
    bottomSpacer = Math.max(0, (total - end) * THREAD_EST_HEIGHT);
  }

  return (
    <div
      ref={threadRef}
      className="ml-4 pl-4 space-y-0 border-l-2 border-border"
    >
      {topSpacer > 0 && <div style={{ height: topSpacer }} />}
      {visibleReplies.map((reply, index) => {
        const agent = resolveAgent(reply.agent, agents, reply.context);
        const isUser = reply.agent === "user";
        const isLast = index === visibleReplies.length - 1 && hiddenCount === 0;
        const isCollapsed = collapsed.has(reply.id);

        // Detect convergence phase from context
        const ctx = reply.context || {};
        const phase = (ctx.convergence_phase as string) || (ctx.consensus_synthesis ? "synthesis" : "");
        const phaseStyle = phase ? PHASE_STYLES[phase] : null;
        const showPhaseDivider = phase && phase !== currentPhase;
        if (phase) currentPhase = phase;
        const isSynthesis = Boolean(ctx.consensus_synthesis);
        const debateRound = ctx.debate_round as number | undefined;

        return (
          <div key={reply.id}>
            {/* Phase divider */}
            {showPhaseDivider && phaseStyle && (
              <div
                className="flex items-center gap-2 py-2 my-1"
                style={{ borderTop: `1px dashed ${phaseStyle.color}25` }}
              >
                <span className="text-[9px]" style={{ color: phaseStyle.color }}>{phaseStyle.icon}</span>
                <span
                  className="text-[8px] font-bold uppercase tracking-[0.15em]"
                  style={{ color: phaseStyle.color }}
                >
                  {phaseStyle.label} Phase
                </span>
                <div className="flex-1 h-px" style={{ background: `${phaseStyle.color}15` }} />
              </div>
            )}

            <div
              className={cn(
                "py-2.5 transition-colors group/reply cv-auto",
                isSynthesis && "rounded-lg px-2.5 -mx-1 my-1 bg-violet-500/[0.04] border border-violet-500/[0.12]",
                !isLast && !isSynthesis && "border-b"
              )}
            >
              <div className="flex items-start gap-2.5">
                {/* Agent avatar */}
                <div className="relative flex-shrink-0">
                  <div
                    className="h-6 w-6 rounded-lg flex items-center justify-center text-xs mt-0.5"
                    style={{
                      background: isUser ? "hsl(var(--primary) / 0.1)" : `${agent.color}12`,
                      border: agent.isDynamic
                        ? `1px dashed ${agent.color}40`
                        : `1px solid ${isUser ? "hsl(var(--primary) / 0.15)" : `${agent.color}20`}`,
                    }}
                  >
                    {agent.avatar}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span
                      className="text-[12px] font-semibold"
                      style={{ color: isUser ? "hsl(var(--primary))" : agent.color }}
                    >
                      {agent.displayName}
                    </span>
                    {/* Agent ID + dynamic badge */}
                    {!isUser && (
                      <span
                        className={cn(
                          "text-[7px] font-bold data-mono px-1 py-0.5 rounded",
                          agent.isDynamic
                            ? "bg-cyan-500/[0.08] text-cyan-400"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {agent.isDynamic ? "DYN" : reply.agent.replace(/[^a-zA-Z0-9]/g, "").slice(0, 4).toUpperCase()}
                      </span>
                    )}
                    {/* Synthesis badge */}
                    {isSynthesis && (
                      <Badge variant="info" className="text-[7px] font-bold uppercase px-1.5 py-0.5">
                        &#x2B21; Consensus
                      </Badge>
                    )}
                    {/* Phase badge */}
                    {phaseStyle && !isSynthesis && (
                      <span
                        className="text-[7px] font-bold uppercase px-1 py-0.5 rounded"
                        style={{
                          background: `${phaseStyle.color}10`,
                          color: phaseStyle.color,
                        }}
                      >
                        {phaseStyle.label}
                      </span>
                    )}
                    {/* Debate round */}
                    {debateRound && (
                      <span className="text-[7px] font-bold data-mono px-1 py-0.5 rounded bg-orange-500/[0.08] text-orange-500">
                        R{debateRound}
                      </span>
                    )}
                    <span className="text-[10px] data-mono text-muted-foreground">
                      {timeAgo(reply.created_at)}
                    </span>
                    {/* Collapse button for long replies */}
                    {reply.content.length > 400 && (
                      <button
                        onClick={() => toggleCollapse(reply.id)}
                        className="text-[9px] data-mono ml-auto opacity-0 group-hover/reply:opacity-100 transition-opacity text-muted-foreground"
                      >
                        {isCollapsed ? "[expand]" : "[collapse]"}
                      </button>
                    )}
                  </div>
                  {/* Role subtitle for agents */}
                  {agent.role && !isUser && (
                    <div className="text-[8px] font-medium mb-1 text-muted-foreground">
                      {agent.role}
                    </div>
                  )}
                  <div
                    className="text-[12.5px] leading-[1.65] transition-all text-muted-foreground"
                    style={{
                      maxHeight: isCollapsed ? "3.3em" : "none",
                      overflow: isCollapsed ? "hidden" : "visible",
                      maskImage: isCollapsed ? "linear-gradient(to bottom, black 60%, transparent)" : "none",
                      WebkitMaskImage: isCollapsed ? "linear-gradient(to bottom, black 60%, transparent)" : "none",
                    }}
                  >
                    {isCollapsed
                      ? <span>{reply.content.slice(0, 260)}{reply.content.length > 260 ? "..." : ""}</span>
                      : <Markdown>{reply.content}</Markdown>
                    }
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
      {bottomSpacer > 0 && <div style={{ height: bottomSpacer }} />}

      {/* Show more / collapse toggle */}
      {hiddenCount > 0 && (
        <button
          onClick={() => setShowAll(true)}
          className="flex items-center gap-2 py-2.5 w-full text-left transition-colors border-t border-dashed border-border hover:bg-accent"
        >
          <div className="flex -space-x-1">
            {replies.slice(INITIAL_VISIBLE, INITIAL_VISIBLE + 3).map((r) => {
              const a = resolveAgent(r.agent, agents, r.context);
              return (
                <span
                  key={r.id}
                  className="inline-flex items-center justify-center h-4 w-4 rounded-full text-[7px] border border-card"
                  style={{
                    background: `${a.color}20`,
                  }}
                >
                  {a.avatar}
                </span>
              );
            })}
          </div>
          <span className="text-[10px] font-medium text-primary">
            Show {hiddenCount} more {hiddenCount === 1 ? "reply" : "replies"}
          </span>
          <svg className="h-3 w-3 ml-auto text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>
      )}
      {showAll && replies.length > INITIAL_VISIBLE && (
        <button
          onClick={() => setShowAll(false)}
          className="flex items-center gap-1.5 py-2 text-[10px] font-medium transition-colors border-t border-dashed border-border text-muted-foreground hover:text-primary"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
          </svg>
          Collapse thread
        </button>
      )}
    </div>
  );
});
