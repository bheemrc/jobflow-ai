"use client";

import { useState, useEffect, useRef, useCallback, useMemo, memo } from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import type { TimelinePost, AgentPersonality, SwarmInfo, BuilderInfo } from "@/lib/use-timeline-events";
import { REALMS, resolveAgent } from "@/lib/use-timeline-events";
import Markdown from "@/components/markdown";
import { ThreadView } from "./thread-view";
import { ReactionBar } from "./reaction-bar";
import { ThinkingIndicator } from "./thinking-indicator";
import { BuilderProgress } from "./builder-progress";
import { VoteButtons } from "./vote-buttons";
import { AgentProfile } from "./agent-profile";
import type { AgentMemory } from "@/lib/agent-memory";

export interface RelatedSignal {
  id: number;
  agent: string;
  preview: string;
  sharedTopics: string[];
}

interface PostCardProps {
  post: TimelinePost;
  agents: Record<string, AgentPersonality>;
  agentMemory?: AgentMemory;
  relatedSignals?: RelatedSignal[];
  thinkingAgents?: string[];
  swarm?: SwarmInfo;
  builders?: BuilderInfo[];
  onReply?: (postId: number, content: string) => void;
  onReact?: (postId: number, emoji: string) => void;
  onPin?: (postId: number, pinned: boolean) => void;
  onDelete?: (postId: number) => void;
  onVote?: (postId: number, direction: 1 | -1) => void;
  onBookmark?: (postId: number) => void;
  isBookmarked?: boolean;
  isCompact?: boolean;
  isFocused?: boolean;
}

const FLAIR_STYLES: Record<string, { bg: string; text: string; icon: string }> = {
  discussion: { bg: "rgba(96, 165, 250, 0.1)", text: "#60A5FA", icon: "\u{1F4AC}" },
  intel: { bg: "rgba(74, 222, 128, 0.1)", text: "#4ADE80", icon: "\u25C9" },
  strategy: { bg: "rgba(167, 139, 250, 0.1)", text: "#A78BFA", icon: "\u265F\uFE0F" },
  debug: { bg: "rgba(249, 115, 22, 0.1)", text: "#F97316", icon: "\u{1F527}" },
  celebration: { bg: "rgba(251, 191, 36, 0.1)", text: "#FBBF24", icon: "\u{1F389}" },
  question: { bg: "rgba(34, 211, 238, 0.1)", text: "#22D3EE", icon: "?" },
};

const AWARD_STYLES: Record<string, { icon: string; label: string; color: string }> = {
  insightful: { icon: "\u{1F4A1}", label: "Insightful", color: "#FBBF24" },
  helpful: { icon: "\u{1F91D}", label: "Helpful", color: "#4ADE80" },
  creative: { icon: "\u{1F3A8}", label: "Creative", color: "#A78BFA" },
  expert: { icon: "\u2B50", label: "Expert", color: "#F97316" },
};

const POST_TYPE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  thought: { bg: "rgba(139, 92, 246, 0.1)", text: "#A78BFA", label: "signal" },
  discovery: { bg: "rgba(74, 222, 128, 0.1)", text: "#4ADE80", label: "discovery" },
  reaction: { bg: "rgba(251, 191, 36, 0.1)", text: "#FCD34D", label: "response" },
  question: { bg: "rgba(96, 165, 250, 0.1)", text: "#93C5FD", label: "inquiry" },
  share: { bg: "rgba(244, 114, 182, 0.1)", text: "#F9A8D4", label: "share" },
  thread: { bg: "rgba(148, 163, 184, 0.08)", text: "#94A3B8", label: "chain" },
};

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
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d`;
  return then.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export const PostCard = memo(function PostCard({
  post,
  agents,
  agentMemory,
  relatedSignals = [],
  thinkingAgents = [],
  onReply,
  onReact,
  onPin,
  onDelete,
  onVote,
  onBookmark,
  isBookmarked = false,
  swarm,
  builders,
  isCompact = false,
  isFocused = false,
}: PostCardProps) {
  const [showThread, setShowThread] = useState(false);
  const [showReplyInput, setShowReplyInput] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [showAwardPicker, setShowAwardPicker] = useState(false);

  const handleGiveAward = useCallback((award: string) => {
    onReact?.(post.id, `award:${award}`);
    setShowAwardPicker(false);
  }, [onReact, post.id]);

  const handleVote = useCallback((dir: 1 | -1) => {
    onVote?.(post.id, dir);
  }, [onVote, post.id]);
  const prevReplyCount = useRef(post.reply_count || 0);
  const cardRef = useRef<HTMLDivElement>(null);

  // Scroll focused card into view
  useEffect(() => {
    if (isFocused && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [isFocused]);

  useEffect(() => {
    const current = post.reply_count || 0;
    if (current > prevReplyCount.current) setShowThread(true);
    prevReplyCount.current = current;
  }, [post.reply_count]);

  // Dynamic agent resolution -- works for ANY agent (static, dynamic, or unknown)
  const agent = useMemo(() => resolveAgent(post.agent, agents, post.context), [post.agent, agents, post.context]);
  const isUser = post.agent === "user";
  const typeStyle = POST_TYPE_STYLES[post.post_type] || POST_TYPE_STYLES.thought;
  const realmData = useMemo(() => post.realm ? REALMS.find((r) => r.id === post.realm) : null, [post.realm]);

  const contextChips = useMemo(() => Object.entries(post.context || {}).filter(
    ([k]) => !["event", "mentioned_by", "in_reply_to", "parent_id", "dynamic_agent", "builder_complete", "material_id", "swarm_wave", "requested_by", "task", "convergence_phase", "consensus_synthesis", "research_curator", "debate_round", "routed_reply", "company", "role", "confidence", "post_id", "job_id", "bot_name", "run_id"].includes(k)
  ), [post.context]);
  const isSynthesis = Boolean(post.context?.consensus_synthesis);
  const replyCount = post.reply_count || 0;

  // Short agent ID for tracking (first 6 chars of agent key)
  const agentId = useMemo(() => post.agent !== "user" ? post.agent.replace(/[^a-zA-Z0-9]/g, "").slice(0, 6).toUpperCase() : null, [post.agent]);

  // Memoized personality trait detection
  const personalityTrait = useMemo(() => {
    if (isUser) return null;
    const c = post.content.toLowerCase();
    if (c.includes("data") || c.includes("research") || c.includes("analysis") || c.includes("statistic")) return { label: "Analytical", color: "#22D3EE" };
    if (c.includes("consider") || c.includes("however") || c.includes("alternatively") || c.includes("caution")) return { label: "Measured", color: "#A78BFA" };
    if (c.includes("recommend") || c.includes("strategy") || c.includes("approach") || c.includes("action")) return { label: "Strategic", color: "#F97316" };
    if (c.includes("creative") || c.includes("innovative") || c.includes("unique") || c.includes("idea")) return { label: "Creative", color: "#F472B6" };
    return null;
  }, [post.content, isUser]);

  // Memoized URL extraction for link previews
  const extractedUrls = useMemo(() => {
    const urlRegex = /https?:\/\/[^\s)>\]]+/g;
    const urls = post.content.match(urlRegex);
    if (!urls || urls.length === 0) return [];
    return [...new Set(urls)].slice(0, 2);
  }, [post.content]);

  const handleSubmitReply = () => {
    if (replyText.trim() && onReply) {
      onReply(post.id, replyText.trim());
      setReplyText("");
      setShowReplyInput(false);
      setShowThread(true);
    }
  };

  return (
    <div
      ref={cardRef}
      className={cn(
        "group relative rounded-2xl transition-all duration-200 cv-auto border post-card-hover",
        isSynthesis
          ? "bg-gradient-to-br from-violet-500/[0.06] to-blue-500/[0.04] border-violet-500/20 shadow-[0_4px_24px_rgba(167,139,250,0.1)]"
          : post.pinned
          ? "bg-gradient-to-br from-blue-500/[0.06] to-violet-500/[0.04] border-blue-500/20"
          : "bg-card border-border hover:border-border hover:shadow-md",
        isFocused && "ring-2 ring-primary"
      )}
    >
      {/* Pinned badge */}
      {post.pinned && (
        <Badge className="absolute -top-2.5 left-5 text-[9px] font-bold uppercase tracking-wider bg-primary text-white shadow-md">
          &#x25C6; Anchored
        </Badge>
      )}
      {/* Synthesis badge */}
      {isSynthesis && !post.pinned && (
        <Badge className="absolute -top-2.5 left-5 text-[9px] font-bold uppercase tracking-wider bg-gradient-to-r from-violet-500 to-indigo-400 text-white shadow-md">
          &#x2B21; Nexus Synthesis
        </Badge>
      )}

      <div className={cn("flex gap-0", (post.pinned || isSynthesis) && "pt-5")}>
        {/* Vote column */}
        {onVote && (
          <div className="flex-shrink-0 py-3 pl-2 pr-0">
            <VoteButtons
              votes={post.votes || 0}
              userVote={post.user_vote || 0}
              onVote={handleVote}
            />
          </div>
        )}

        <div className={cn("flex-1 p-4", !onVote ? "pl-4" : "pl-2", isCompact && "py-3")}>
          {/* Realm tag + Flair */}
          {(realmData || post.flair) && (
            <div className="mb-2 flex items-center gap-1.5">
              {realmData && (
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider"
                  style={{
                    background: `${realmData.color}10`,
                    color: realmData.color,
                    border: `1px solid ${realmData.color}25`,
                  }}
                >
                  <span className="text-[9px]">{realmData.icon}</span>
                  {realmData.name}
                </span>
              )}
              {post.flair && FLAIR_STYLES[post.flair] && (
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold capitalize"
                  style={{
                    background: FLAIR_STYLES[post.flair].bg,
                    color: FLAIR_STYLES[post.flair].text,
                    border: `1px solid ${FLAIR_STYLES[post.flair].text}25`,
                  }}
                >
                  <span className="text-[8px]">{FLAIR_STYLES[post.flair].icon}</span>
                  {post.flair}
                </span>
              )}
            </div>
          )}

          {/* Header row */}
          <div className="flex items-center gap-3 mb-3">
            {/* Agent avatar with color ring + profile hover */}
            <AgentProfile
              agentKey={post.agent}
              displayName={agent.displayName}
              avatar={agent.avatar}
              color={agent.color}
              bio={agent.bio}
              role={agent.role}
              isDynamic={agent.isDynamic}
              reputation={post.votes}
              memory={agentMemory}
            >
              <div className="relative flex-shrink-0 cursor-pointer">
                <div
                  className="h-9 w-9 rounded-xl flex items-center justify-center text-base transition-transform duration-200 group-hover:scale-105"
                  style={{
                    background: isUser
                      ? "hsl(var(--primary) / 0.1)"
                      : `${agent.color}12`,
                    border: `1.5px solid ${isUser ? "hsl(var(--primary) / 0.2)" : `${agent.color}30`}`,
                  }}
                >
                  {agent.avatar}
                </div>
                {/* Dynamic agent indicator */}
                {agent.isDynamic && (
                  <span
                    className="absolute -top-1 -right-1 h-3 w-3 rounded-full flex items-center justify-center text-[6px] font-bold bg-cyan-400 text-slate-900 shadow-[0_0_6px_rgba(34,211,238,0.4)]"
                    title="Dynamically spawned agent"
                  >
                    &#x25C7;
                  </span>
                )}
                {/* Memory indicator -- agent has rich context */}
                {!agent.isDynamic && agentMemory && agentMemory.totalPosts >= 3 && (
                  <span
                    className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full flex items-center justify-center text-[7px] bg-card"
                    style={{ border: `1px solid ${agent.color}30` }}
                    title={`Remembers ${agentMemory.totalPosts} conversations`}
                  >
                    &#x1F9E0;
                  </span>
                )}
              </div>
            </AgentProfile>

            {/* Name + meta */}
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className="text-[13px] font-semibold truncate"
                    style={{ color: isUser ? "hsl(var(--primary))" : agent.color }}
                  >
                    {agent.displayName}
                  </span>
                  {/* Agent ID badge for tracking */}
                  {agentId && (
                    <span
                      className={cn(
                        "text-[7px] font-bold data-mono px-1 py-0.5 rounded",
                        agent.isDynamic
                          ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/15"
                          : "bg-muted text-muted-foreground"
                      )}
                      title={`Agent ID: ${post.agent}`}
                    >
                      {agent.isDynamic ? "DYN" : agentId}
                    </span>
                  )}
                </div>
                {/* Agent role + personality traits */}
                {agent.role && !isUser && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] font-medium text-muted-foreground">
                      {agent.role}
                    </span>
                    {/* Personality style indicator based on post content analysis */}
                    {personalityTrait && (
                      <span
                        className="text-[7px] font-bold uppercase px-1 py-0.5 rounded"
                        style={{ background: `${personalityTrait.color}10`, color: personalityTrait.color }}
                      >
                        {personalityTrait.label}
                      </span>
                    )}
                  </div>
                )}
              </div>
              <span className="text-[10px] data-mono ml-auto shrink-0 text-muted-foreground">
                {timeAgo(post.created_at)}
              </span>
              {post.post_type !== "thought" && (
                <span
                  className="flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-wider shrink-0"
                  style={{ background: typeStyle.bg, color: typeStyle.text }}
                >
                  {typeStyle.label}
                </span>
              )}
            </div>

            {/* Hover actions */}
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shrink-0">
              {onBookmark && (
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn("h-7 w-7", isBookmarked ? "text-amber-400" : "text-muted-foreground hover:text-amber-400")}
                  onClick={() => onBookmark(post.id)}
                  title={isBookmarked ? "Remove bookmark" : "Bookmark"}
                  aria-label={isBookmarked ? "Remove bookmark" : "Bookmark this signal"}
                >
                  <svg className="h-3.5 w-3.5" fill={isBookmarked ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                  </svg>
                </Button>
              )}
              {onPin && (
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn("h-7 w-7", post.pinned ? "text-primary" : "text-muted-foreground")}
                  onClick={() => onPin(post.id, !post.pinned)}
                  title={post.pinned ? "Unanchor" : "Anchor"}
                >
                  <svg className="h-3.5 w-3.5" fill={post.pinned ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 3.75V16.5L12 14.25 7.5 16.5V3.75" />
                  </svg>
                </Button>
              )}
              {onDelete && isUser && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  onClick={() => onDelete(post.id)}
                  title="Delete"
                >
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </Button>
              )}
            </div>
          </div>

          {/* Content */}
          <div className="text-[13.5px] leading-[1.65] mb-3 text-foreground">
            <Markdown>{post.content}</Markdown>
          </div>

          {/* Rich link previews for URLs in content */}
          {extractedUrls.length > 0 && (
              <div className="flex flex-col gap-1.5 mb-3">
                {extractedUrls.map((url) => {
                  let domain = "";
                  try { domain = new URL(url).hostname.replace("www.", ""); } catch { domain = url; }
                  const favicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=16`;
                  return (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all duration-150 group/link bg-muted border border-border hover:border-primary hover:bg-accent"
                    >
                      <img
                        src={favicon}
                        alt=""
                        className="h-4 w-4 rounded shrink-0"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-[10px] font-semibold truncate text-primary">
                          {domain}
                        </div>
                        <div className="text-[9px] truncate data-mono text-muted-foreground">
                          {url.length > 80 ? url.slice(0, 80) + "..." : url}
                        </div>
                      </div>
                      <svg
                        className="h-3 w-3 shrink-0 opacity-0 group-hover/link:opacity-100 transition-opacity text-muted-foreground"
                        fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                      </svg>
                    </a>
                  );
                })}
              </div>
          )}

          {/* Convergence indicator (swarm) */}
          {swarm && swarm.started && (
            <div className="mb-3 animate-fade-in">
              <div
                className={cn(
                  "rounded-xl overflow-hidden border",
                  swarm.complete
                    ? "bg-green-400/[0.04] border-green-400/[0.12]"
                    : "bg-indigo-400/[0.04] border-indigo-400/[0.12]"
                )}
              >
                {/* Phase progress bar */}
                {!swarm.complete && (
                  <div className="flex h-1">
                    {(["research", "debate", "synthesis"] as const).map((phase, i) => {
                      const currentIdx = swarm.phase === "research" ? 0 : swarm.phase === "debate" ? 1 : swarm.phase === "synthesis" ? 2 : -1;
                      const colors = ["#22D3EE", "#A78BFA", "#4ADE80"];
                      const isActive = i === currentIdx;
                      const isDone = i < currentIdx || swarm.complete;
                      return (
                        <div
                          key={phase}
                          className="flex-1 transition-all duration-500"
                          style={{
                            background: isDone
                              ? colors[i]
                              : isActive
                              ? `linear-gradient(90deg, ${colors[i]}, ${colors[i]}60)`
                              : "rgba(255,255,255,0.03)",
                            opacity: isDone ? 0.8 : isActive ? 1 : 0.3,
                            animation: isActive ? "phase-pulse 1.5s ease-in-out infinite" : "none",
                          }}
                        />
                      );
                    })}
                  </div>
                )}

                <div className="px-3 py-2.5">
                  {/* Phase steps */}
                  <div className="flex items-center gap-3 mb-2">
                    {(["research", "debate", "synthesis"] as const).map((phase, i) => {
                      const currentIdx = swarm.phase === "research" ? 0 : swarm.phase === "debate" ? 1 : swarm.phase === "synthesis" ? 2 : -1;
                      const icons = ["\u25C8", "\u26A1", "\u2B21"];
                      const labels = ["Research", "Debate", "Synthesis"];
                      const colors = ["#22D3EE", "#A78BFA", "#4ADE80"];
                      const isActive = i === currentIdx && !swarm.complete;
                      const isDone = i < currentIdx || swarm.complete;
                      return (
                        <div key={phase} className="flex items-center gap-1.5">
                          <span
                            className="text-[10px] transition-all duration-300"
                            style={{
                              color: isActive ? colors[i] : isDone ? colors[i] : undefined,
                              opacity: isActive ? 1 : isDone ? 0.7 : 0.35,
                              filter: isActive ? `drop-shadow(0 0 4px ${colors[i]}60)` : "none",
                            }}
                          >
                            {isDone && !isActive ? "\u2713" : icons[i]}
                          </span>
                          <span
                            className="text-[9px] font-bold uppercase tracking-wider transition-all duration-300"
                            style={{
                              color: isActive ? colors[i] : isDone ? colors[i] : undefined,
                              opacity: isActive ? 1 : isDone ? 0.6 : 0.3,
                            }}
                          >
                            {labels[i]}
                          </span>
                          {i < 2 && (
                            <span className="text-[8px] mx-0.5 text-muted-foreground opacity-30">\u2192</span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Status line + agents */}
                  <div className="flex items-center gap-2">
                    <span className={cn("text-[11px] font-semibold", swarm.complete ? "text-green-400/90" : "text-indigo-400/90")}>
                      {swarm.complete
                        ? `Convergence complete \u2014 ${swarm.activations} minds contributed`
                        : `${swarm.activations}/${swarm.maxActivations} minds converging`}
                    </span>
                    {!swarm.complete && (
                      <span className="inline-block h-1.5 w-1.5 rounded-full animate-pulse bg-indigo-400" />
                    )}
                    {swarm.agents.length > 0 && (
                      <div className="flex -space-x-1 ml-auto">
                        {swarm.agents.slice(0, 6).map((a) => {
                          const resolved = resolveAgent(a, agents);
                          return (
                            <span
                              key={a}
                              className="inline-flex items-center justify-center h-5 w-5 rounded-full text-[9px] transition-all duration-200 border-[1.5px] border-card"
                              style={{ background: `${resolved.color}20` }}
                              title={resolved.displayName}
                            >
                              {resolved.avatar}
                            </span>
                          );
                        })}
                        {swarm.agents.length > 6 && (
                          <span className="text-[9px] data-mono ml-1.5 self-center text-muted-foreground">
                            +{swarm.agents.length - 6}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Agent coordination flow -- shows handoff sequence */}
                  {swarm.agents.length >= 2 && (
                    <div className="mt-2 pt-2 border-t border-dashed border-indigo-400/10">
                      <div className="flex items-center gap-1 mb-1.5">
                        <span className="text-[7px] font-bold uppercase tracking-wider text-muted-foreground">
                          Coordination Flow
                        </span>
                      </div>
                      <div className="flex items-center gap-0.5 overflow-x-auto">
                        {swarm.agents.slice(0, 8).map((a, i) => {
                          const resolved = resolveAgent(a, agents);
                          const phaseIdx = swarm.phase === "research" ? 0 : swarm.phase === "debate" ? 1 : 2;
                          const agentPhase = Math.min(Math.floor(i / Math.max(1, Math.ceil(swarm.agents.length / 3))), 2);
                          const phaseColors = ["#22D3EE", "#A78BFA", "#4ADE80"];
                          return (
                            <div key={a} className="flex items-center gap-0.5">
                              <div
                                className="flex items-center gap-1 px-1.5 py-0.5 rounded-md"
                                style={{
                                  background: `${resolved.color}08`,
                                  border: `1px solid ${resolved.color}15`,
                                }}
                                title={`${resolved.displayName} \u2014 ${["Research", "Debate", "Synthesis"][agentPhase]}`}
                              >
                                <span className="text-[8px]">{resolved.avatar}</span>
                                <span className="text-[7px] font-medium data-mono" style={{ color: resolved.color }}>
                                  {resolved.displayName.split(" ")[0]}
                                </span>
                              </div>
                              {i < Math.min(swarm.agents.length, 8) - 1 && (
                                <span
                                  className="text-[7px] opacity-60"
                                  style={{
                                    color: swarm.complete ? "#4ADE80" : phaseColors[Math.min(agentPhase, phaseIdx)],
                                  }}
                                >
                                  \u2192
                                </span>
                              )}
                            </div>
                          );
                        })}
                        {swarm.agents.length > 8 && (
                          <span className="text-[7px] data-mono pl-1 text-muted-foreground">
                            +{swarm.agents.length - 8}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Builder progress */}
          {builders && builders.length > 0 && <BuilderProgress builders={builders} />}

          {/* Metadata: confidence, context chips */}
          {(() => {
            const confidence = post.context?.confidence as string | undefined;
            const company = post.context?.company as string | undefined;
            const role = post.context?.role as string | undefined;
            const hasMetadata = contextChips.length > 0 || confidence || company || role;
            if (!hasMetadata) return null;
            return (
              <div className="flex flex-wrap items-center gap-1.5 mb-3">
                {/* Company chip */}
                {company && (
                  <Badge variant="info" className="gap-1 text-[9px] font-bold">
                    <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21" />
                    </svg>
                    {String(company)}
                  </Badge>
                )}
                {/* Role chip */}
                {role && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[9px] font-bold bg-violet-500/[0.08] text-violet-400 border border-violet-500/15">
                    {String(role)}
                  </span>
                )}
                {/* Confidence indicator */}
                {confidence && (
                  <Badge
                    variant={confidence === "high" ? "success" : confidence === "medium" ? "warning" : "destructive"}
                    className="gap-1 text-[9px] font-bold"
                  >
                    <span className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      confidence === "high" ? "bg-green-400" : confidence === "medium" ? "bg-amber-400" : "bg-red-500"
                    )} />
                    {String(confidence)} confidence
                  </Badge>
                )}
                {/* Remaining context chips */}
                {contextChips
                  .filter(([k]) => !["company", "role", "confidence"].includes(k))
                  .map(([key, value]) => (
                    <Badge key={key} variant="secondary" className="gap-1 text-[9px]">
                      <span className="h-1 w-1 rounded-full bg-muted-foreground" />
                      {String(value)}
                    </Badge>
                  ))
                }
              </div>
            );
          })()}

          {/* Reactions */}
          {Object.keys(post.reactions).length > 0 && (
            <div className="mb-3"><ReactionBar reactions={post.reactions} agents={agents} /></div>
          )}

          {/* Awards display */}
          {post.awards && post.awards.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mb-3">
              {post.awards.map((award, i) => {
                const style = AWARD_STYLES[award];
                if (!style) return null;
                return (
                  <span
                    key={`${award}-${i}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold"
                    style={{
                      background: `${style.color}10`,
                      color: style.color,
                      border: `1px solid ${style.color}20`,
                    }}
                    title={style.label}
                  >
                    {style.icon} {style.label}
                  </span>
                );
              })}
            </div>
          )}

          {/* Action bar */}
          <div className="flex items-center gap-1 pt-2 border-t">
            <button
              onClick={() => setShowReplyInput(!showReplyInput)}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all hover:bg-accent hover:text-primary",
                showReplyInput ? "text-primary" : "text-muted-foreground"
              )}
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 20.25c4.97 0 9-3.694 9-8.25s-4.03-8.25-9-8.25S3 7.444 3 12c0 2.104.859 4.023 2.273 5.48.432.447.74 1.04.586 1.641a4.483 4.483 0 01-.923 1.785A5.969 5.969 0 006 21c1.282 0 2.47-.402 3.445-1.087.81.22 1.668.337 2.555.337z" />
              </svg>
              Reply
              {replyCount > 0 && <span className="data-mono text-muted-foreground">{replyCount}</span>}
            </button>

            <button
              onClick={() => onReact?.(post.id, "\u26A1")}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all text-muted-foreground hover:bg-accent hover:text-orange-500"
            >
              &#x26A1; Resonate
            </button>

            {/* Award button */}
            <div className="relative">
              <button
                onClick={() => setShowAwardPicker(!showAwardPicker)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all hover:bg-accent hover:text-amber-400",
                  showAwardPicker ? "text-amber-400" : "text-muted-foreground"
                )}
              >
                &#x1F3C5; Award
              </button>
              {showAwardPicker && (
                <Card className="absolute left-0 bottom-full mb-1 flex items-center gap-1 p-1.5 z-50 animate-scale-in shadow-xl">
                  {Object.entries(AWARD_STYLES).map(([key, style]) => (
                    <button
                      key={key}
                      onClick={() => handleGiveAward(key)}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition-all whitespace-nowrap text-muted-foreground hover:text-foreground hover:bg-accent"
                      title={style.label}
                    >
                      <span>{style.icon}</span>
                      <span>{style.label}</span>
                    </button>
                  ))}
                </Card>
              )}
            </div>

            {replyCount > 0 && (
              <button
                onClick={() => setShowThread(!showThread)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all ml-auto text-primary hover:bg-primary/10"
              >
                <svg
                  className="h-3.5 w-3.5 transition-transform duration-200"
                  fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"
                  style={{ transform: showThread ? "rotate(180deg)" : "rotate(0deg)" }}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
                {showThread ? "Collapse" : `${replyCount} ${replyCount === 1 ? "chain" : "chains"}`}
              </button>
            )}
          </div>

          {/* Reply input */}
          {showReplyInput && (
            <div className="mt-3 flex gap-2 animate-fade-in-up">
              <Input
                type="text"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmitReply()}
                placeholder="Add to the chain... (@agent to summon)"
                className="flex-1 rounded-xl text-[13px]"
                autoFocus
              />
              <Button
                onClick={handleSubmitReply}
                disabled={!replyText.trim()}
                size="sm"
                className="px-4 rounded-xl text-[12px] font-semibold"
              >
                Send
              </Button>
            </div>
          )}

          {/* Thinking indicator */}
          {thinkingAgents.length > 0 && (
            <div className="mt-3 animate-fade-in">
              <ThinkingIndicator agents={thinkingAgents} personalities={agents} />
            </div>
          )}

          {/* Thread view */}
          {showThread && (
            <div className="mt-3 animate-fade-in">
              <ThreadView postId={post.id} replyCount={replyCount} agents={agents} onReply={onReply} />
            </div>
          )}

          {/* Related signals cross-reference */}
          {relatedSignals.length > 0 && !isCompact && (
            <div className="mt-3 pt-2.5 space-y-1.5 border-t border-dashed">
              <div className="flex items-center gap-1.5">
                <span className="text-[8px] font-bold uppercase tracking-wider text-muted-foreground">
                  &#x25C8; Related Signals
                </span>
              </div>
              {relatedSignals.slice(0, 2).map((rel) => {
                const relAgent = resolveAgent(rel.agent, agents);
                return (
                  <div
                    key={rel.id}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors cursor-pointer bg-muted hover:bg-accent"
                  >
                    <span
                      className="h-4 w-4 rounded flex items-center justify-center text-[8px] shrink-0"
                      style={{ background: `${relAgent.color}12`, border: `1px solid ${relAgent.color}20` }}
                    >
                      {relAgent.avatar}
                    </span>
                    <span className="text-[10px] truncate flex-1 text-muted-foreground">
                      {rel.preview}
                    </span>
                    <div className="flex gap-0.5 shrink-0">
                      {rel.sharedTopics.slice(0, 2).map((t) => (
                        <span
                          key={t}
                          className="text-[7px] px-1 py-0.5 rounded bg-primary/[0.08] text-primary"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});
