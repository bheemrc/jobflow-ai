"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useArenaSession, type AgentRole, type ArenaAgent } from "@/lib/use-arena-session";
import ReactMarkdown from "react-markdown";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Swords,
  Send,
  Square,
  RotateCcw,
  Zap,
  Shield,
  Crown,
  Clock,
  Hash,
  Trophy,
  ChevronDown,
} from "lucide-react";

/* ── Agent theme config ── */

const AGENT_THEME: Record<
  AgentRole,
  {
    color: string;
    bgTint: string;
    borderActive: string;
    glowActive: string;
    badgeVariant: "info" | "warning" | "success";
    icon: typeof Zap;
    tagline: string;
    waitingQuote: string;
  }
> = {
  alpha: {
    color: "text-blue-600",
    bgTint: "bg-blue-50",
    borderActive: "border-blue-400",
    glowActive: "shadow-[0_0_24px_-4px_rgba(59,130,246,0.3)]",
    badgeVariant: "info",
    icon: Zap,
    tagline: "First to strike. Sets the baseline.",
    waitingQuote: "",
  },
  beta: {
    color: "text-amber-600",
    bgTint: "bg-amber-50",
    borderActive: "border-amber-400",
    glowActive: "shadow-[0_0_24px_-4px_rgba(245,158,11,0.3)]",
    badgeVariant: "warning",
    icon: Shield,
    tagline: "Reviews. Challenges. Improves.",
    waitingQuote: "Watching Alpha work... I'll do better.",
  },
  gamma: {
    color: "text-emerald-600",
    bgTint: "bg-emerald-50",
    borderActive: "border-emerald-400",
    glowActive: "shadow-[0_0_24px_-4px_rgba(16,185,129,0.3)]",
    badgeVariant: "success",
    icon: Crown,
    tagline: "The final word. Definitive.",
    waitingQuote: "Let them debate... I'll settle it.",
  },
};

const STATUS_LABELS: Record<string, string> = {
  idle: "Standing By",
  waiting: "On Deck",
  thinking: "Thinking",
  streaming: "Writing",
  done: "Complete",
  error: "Error",
};

/* ── Elapsed time display ── */

function ElapsedTime({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return (
    <span className="font-mono text-[10px]">
      {mins > 0 ? `${mins}m ` : ""}{secs}s
    </span>
  );
}

/* ── Thinking dots animation ── */

function ThinkingDots() {
  return (
    <span className="inline-flex gap-0.5 ml-1">
      <span className="h-1 w-1 rounded-full bg-current animate-typing-dot" style={{ animationDelay: "0ms" }} />
      <span className="h-1 w-1 rounded-full bg-current animate-typing-dot" style={{ animationDelay: "200ms" }} />
      <span className="h-1 w-1 rounded-full bg-current animate-typing-dot" style={{ animationDelay: "400ms" }} />
    </span>
  );
}

/* ── Markdown components (minimal) ── */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MD_COMPONENTS: Record<string, React.ComponentType<any>> = {
  h1: ({ children }) => <h1 className="text-base font-bold mt-4 mb-2 text-foreground">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-bold mt-4 mb-2 text-foreground">{children}</h2>,
  h3: ({ children }) => <h3 className="text-[13px] font-semibold mt-3 mb-1.5 text-foreground">{children}</h3>,
  p: ({ children }) => <p className="text-[13px] leading-relaxed mb-2 text-muted-foreground">{children}</p>,
  ul: ({ children }) => <ul className="list-disc list-outside ml-4 mb-2 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-outside ml-4 mb-2 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="text-[13px] leading-relaxed text-muted-foreground">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="text-muted-foreground">{children}</em>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline text-primary hover:no-underline">
      {children}
    </a>
  ),
  code: ({ children, className }) => {
    if (!className) {
      return <code className="px-1 py-0.5 rounded text-xs font-mono bg-muted text-foreground">{children}</code>;
    }
    return (
      <pre className="p-3 rounded-lg overflow-x-auto text-xs my-2 bg-muted">
        <code className="font-mono text-muted-foreground">{children}</code>
      </pre>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 pl-3 my-2 italic border-border text-muted-foreground text-[13px]">
      {children}
    </blockquote>
  ),
};

/* ── Content renderer: plain text while streaming, markdown when done ── */

function AgentContent({ content, isStreaming }: { content: string; isStreaming: boolean }) {
  if (isStreaming) {
    // Plain text while streaming — zero parse overhead, instant updates
    return (
      <div className="text-[13px] leading-relaxed text-muted-foreground whitespace-pre-wrap break-words">
        {content}
        <span className="inline-block w-1.5 h-4 ml-0.5 align-middle animate-pulse rounded-sm bg-primary" />
      </div>
    );
  }

  // Full markdown render only when done (runs once)
  return (
    <div className="prose-arena animate-fade-in">
      <ReactMarkdown components={MD_COMPONENTS}>{content}</ReactMarkdown>
    </div>
  );
}

/* ── Single Agent Column ── */

function AgentColumn({
  agent,
  stepNumber,
  isActive,
}: {
  agent: ArenaAgent;
  stepNumber: number;
  isActive: boolean;
}) {
  const theme = AGENT_THEME[agent.role];
  const Icon = theme.icon;
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const isWorking = agent.status === "thinking" || agent.status === "streaming";
  const isDone = agent.status === "done";
  const isIdle = agent.status === "idle" || agent.status === "waiting";

  // Auto-scroll while streaming
  useEffect(() => {
    if (agent.status === "streaming" && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [agent.content, agent.status]);

  return (
    <div
      className={cn(
        "flex flex-col rounded-xl border transition-all duration-500 min-h-0",
        isActive && !isDone && theme.borderActive,
        isActive && !isDone && theme.glowActive,
        isDone && "border-border",
        isIdle && "border-border opacity-60",
        "bg-card",
      )}
    >
      {/* Agent header */}
      <div
        className={cn(
          "px-4 py-3 rounded-t-xl border-b transition-colors duration-300",
          isWorking && theme.bgTint,
          isDone && "bg-muted/30",
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-300",
                isWorking && `${theme.bgTint} ${theme.color}`,
                isDone && "bg-muted text-muted-foreground",
                isIdle && "bg-muted/50 text-muted-foreground/50",
              )}
            >
              <Icon className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className={cn("text-[13px] font-bold", isIdle ? "text-muted-foreground" : "text-foreground")}>
                  {agent.name}
                </span>
                <span className={cn("text-[10px] font-medium", theme.color, isIdle && "opacity-50")}>
                  {agent.title}
                </span>
              </div>
              <p className={cn("text-[10px] mt-0.5", isIdle ? "text-muted-foreground/50" : "text-muted-foreground")}>
                {theme.tagline}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Step number */}
            <div
              className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-bold",
                isActive && !isIdle
                  ? `${theme.bgTint} ${theme.color}`
                  : "bg-muted text-muted-foreground",
              )}
            >
              {stepNumber}
            </div>
          </div>
        </div>

        {/* Status bar */}
        <div className="flex items-center justify-between mt-2.5">
          <Badge
            variant={isDone ? theme.badgeVariant : agent.status === "error" ? "destructive" : "secondary"}
            className={cn(
              "text-[9px] font-mono uppercase tracking-wide",
              isWorking && "animate-pulse",
            )}
          >
            {isWorking && <span className="mr-1">●</span>}
            {STATUS_LABELS[agent.status] || agent.status}
          </Badge>

          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            {agent.startedAt && (
              <span className="flex items-center gap-0.5">
                <Clock className="h-2.5 w-2.5" />
                {agent.finishedAt ? (
                  <span className="font-mono">
                    {Math.round((agent.finishedAt - agent.startedAt) / 1000)}s
                  </span>
                ) : (
                  <ElapsedTime startedAt={agent.startedAt} />
                )}
              </span>
            )}
            {agent.wordCount > 0 && (
              <span className="flex items-center gap-0.5">
                <Hash className="h-2.5 w-2.5" />
                <span className="font-mono">{agent.wordCount}w</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 min-h-0 relative">
        {/* Collapse toggle for done state on mobile */}
        {isDone && (
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="lg:hidden w-full flex items-center justify-center gap-1 py-1.5 text-[10px] text-muted-foreground hover:text-foreground border-b"
          >
            {isCollapsed ? "Show response" : "Collapse"}
            <ChevronDown className={cn("h-3 w-3 transition-transform", !isCollapsed && "rotate-180")} />
          </button>
        )}

        <div
          ref={scrollRef}
          className={cn(
            "overflow-y-auto px-4 py-3",
            isCollapsed ? "max-h-0 overflow-hidden p-0" : "max-h-[500px] lg:max-h-none lg:h-full",
          )}
        >
          {/* Idle / Waiting state */}
          {isIdle && (
            <div className="flex items-center justify-center h-32 lg:h-full">
              <div className="text-center">
                <Icon className={cn("h-8 w-8 mx-auto mb-2", theme.color, "opacity-20")} />
                <p className="text-[11px] text-muted-foreground/50">
                  {agent.status === "waiting" && theme.waitingQuote
                    ? theme.waitingQuote
                    : "Awaiting deployment"}
                </p>
              </div>
            </div>
          )}

          {/* Thinking state */}
          {agent.status === "thinking" && (
            <div className="flex items-center justify-center h-32 lg:h-full">
              <div className="text-center">
                <div
                  className={cn(
                    "h-10 w-10 rounded-full mx-auto mb-3 flex items-center justify-center",
                    theme.bgTint,
                  )}
                >
                  <div
                    className={cn(
                      "h-6 w-6 rounded-full border-2 border-t-transparent animate-spin",
                      agent.role === "alpha" && "border-blue-400",
                      agent.role === "beta" && "border-amber-400",
                      agent.role === "gamma" && "border-emerald-400",
                    )}
                  />
                </div>
                <p className={cn("text-[12px] font-medium", theme.color)}>
                  {agent.thinkingMessage}
                  <ThinkingDots />
                </p>
              </div>
            </div>
          )}

          {/* Streaming / Done content */}
          {(agent.status === "streaming" || agent.status === "done") && agent.content && (
            <AgentContent content={agent.content} isStreaming={agent.status === "streaming"} />
          )}

          {/* Error state */}
          {agent.status === "error" && (
            <div className="flex items-center justify-center h-32 lg:h-full">
              <div className="text-center">
                <p className="text-[12px] text-destructive font-medium">
                  {agent.error || "Something went wrong"}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Progress connector between columns ── */

function ProgressConnector({ from, to }: { from: ArenaAgent; to: ArenaAgent }) {
  const fromDone = from.status === "done";
  const toActive = to.status !== "idle" && to.status !== "waiting";

  return (
    <div className="hidden lg:flex items-center justify-center w-6 shrink-0">
      <div className="flex flex-col items-center gap-1">
        <div
          className={cn(
            "h-8 w-[2px] rounded-full transition-all duration-500",
            fromDone ? "bg-primary" : "bg-border",
          )}
        />
        <div
          className={cn(
            "h-2.5 w-2.5 rounded-full border-2 transition-all duration-500",
            toActive
              ? "bg-primary border-primary scale-110"
              : fromDone
                ? "bg-background border-primary animate-pulse"
                : "bg-background border-border",
          )}
        />
        <div
          className={cn(
            "h-8 w-[2px] rounded-full transition-all duration-500",
            toActive ? "bg-primary" : "bg-border",
          )}
        />
      </div>
    </div>
  );
}

/* ── Main Arena Page ── */

export default function ArenaPage() {
  const { session, agents, startArena, stopArena, resetArena } = useArenaSession();
  const [topic, setTopic] = useState("");
  const [isStarting, setIsStarting] = useState(false);

  const alpha = agents[0];
  const beta = agents[1];
  const gamma = agents[2];

  const isRunning = session?.status === "running";
  const isComplete = session?.status === "complete";

  const activeAgentIndex = useMemo(() => {
    if (gamma.status === "thinking" || gamma.status === "streaming") return 2;
    if (beta.status === "thinking" || beta.status === "streaming") return 1;
    if (alpha.status === "thinking" || alpha.status === "streaming") return 0;
    return -1;
  }, [alpha.status, beta.status, gamma.status]);

  const handleStart = useCallback(async () => {
    if (!topic.trim() || isStarting) return;
    setIsStarting(true);
    await startArena(topic.trim());
    setIsStarting(false);
  }, [topic, isStarting, startArena]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleStart();
    }
  };

  const EXAMPLE_TOPICS = [
    "Best database for real-time analytics: ClickHouse vs TimescaleDB vs DuckDB",
    "How to build a production-ready WebSocket server in Rust",
    "Compare Kubernetes vs Docker Swarm vs Nomad for container orchestration",
  ];

  return (
    <div className="h-full flex flex-col p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-lg">
            <Swords className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Agent Arena</h1>
            <p className="text-sm text-muted-foreground">
              Three agents compete to deliver the best answer
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {session && (
            <>
              {/* Progress indicator */}
              <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[11px] font-medium bg-card">
                {agents.map((a, i) => (
                  <div key={a.role} className="flex items-center gap-1">
                    <div
                      className={cn(
                        "h-2 w-2 rounded-full transition-all duration-300",
                        a.status === "done" && "bg-success",
                        (a.status === "thinking" || a.status === "streaming") && "bg-primary animate-pulse",
                        a.status === "waiting" && "bg-border",
                        a.status === "idle" && "bg-border",
                        a.status === "error" && "bg-destructive",
                      )}
                    />
                    {i < 2 && <div className="w-3 h-px bg-border" />}
                  </div>
                ))}
              </div>

              {isRunning ? (
                <Button
                  onClick={stopArena}
                  variant="outline"
                  size="sm"
                  className="text-[12px] font-medium text-destructive border-destructive/30"
                >
                  <Square className="h-3 w-3 mr-1.5" />
                  Stop
                </Button>
              ) : (
                <Button
                  onClick={resetArena}
                  variant="outline"
                  size="sm"
                  className="text-[12px] font-medium"
                >
                  <RotateCcw className="h-3 w-3 mr-1.5" />
                  New Arena
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Topic input */}
      <Card className="p-4 shrink-0">
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="text-[10px] font-bold uppercase tracking-wide mb-1.5 block text-muted-foreground">
              Research Question
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter a topic for the agents to compete on..."
              disabled={isRunning}
              className={cn(
                "w-full px-3 py-2.5 rounded-lg text-sm border bg-background text-foreground",
                "placeholder:text-muted-foreground/50",
                "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
                isRunning && "opacity-50 cursor-not-allowed",
              )}
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={handleStart}
              disabled={!topic.trim() || isStarting || isRunning}
              className="px-5 py-2.5 bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white hover:from-violet-600 hover:to-fuchsia-600 border-0 shadow-md"
            >
              <Send className="h-3.5 w-3.5 mr-1.5" />
              {isStarting ? "Launching..." : "Launch Arena"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Session info bar */}
      {session && (
        <div className="flex items-center gap-3 px-1 shrink-0">
          <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
            <span className="font-medium text-foreground truncate max-w-[400px]">
              &ldquo;{session.topic}&rdquo;
            </span>
            {session.startedAt && (
              <span className="flex items-center gap-1 shrink-0">
                <Clock className="h-3 w-3" />
                <ElapsedTime startedAt={session.startedAt} />
              </span>
            )}
          </div>
          {isComplete && (
            <Badge variant="success" className="text-[9px] font-bold uppercase tracking-wide ml-auto shrink-0">
              <Trophy className="h-2.5 w-2.5 mr-1" />
              Arena Complete
            </Badge>
          )}
        </div>
      )}

      {/* Main content: 3-column arena OR empty state */}
      {session ? (
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-3">
          {/* Agent Alpha */}
          <div className="flex-1 min-h-0 flex flex-col min-w-0">
            <AgentColumn agent={alpha} stepNumber={1} isActive={activeAgentIndex === 0 || alpha.status === "done"} />
          </div>

          <ProgressConnector from={alpha} to={beta} />

          {/* Agent Beta */}
          <div className="flex-1 min-h-0 flex flex-col min-w-0">
            <AgentColumn agent={beta} stepNumber={2} isActive={activeAgentIndex === 1 || beta.status === "done"} />
          </div>

          <ProgressConnector from={beta} to={gamma} />

          {/* Agent Gamma */}
          <div className="flex-1 min-h-0 flex flex-col min-w-0">
            <AgentColumn agent={gamma} stepNumber={3} isActive={activeAgentIndex === 2 || gamma.status === "done"} />
          </div>
        </div>
      ) : (
        /* Empty state */
        <Card className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-lg px-8">
            <div className="inline-flex h-20 w-20 items-center justify-center rounded-2xl mb-6 bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border border-violet-500/20">
              <Swords className="h-10 w-10 text-violet-500/60" />
            </div>
            <h2 className="text-xl font-bold mb-2 text-foreground">Launch the Arena</h2>
            <p className="text-sm mb-6 text-muted-foreground leading-relaxed">
              Three AI agents compete head-to-head. Agent Alpha pioneers,
              Agent Beta challenges, and Agent Gamma delivers the final verdict.
            </p>

            {/* How it works */}
            <div className="flex items-center justify-center gap-6 mb-8">
              {[
                { icon: Zap, label: "Alpha Pioneers", color: "text-blue-500" },
                { icon: Shield, label: "Beta Challenges", color: "text-amber-500" },
                { icon: Crown, label: "Gamma Decides", color: "text-emerald-500" },
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className={cn("flex h-7 w-7 items-center justify-center rounded-lg bg-muted", step.color)}>
                    <step.icon className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-[11px] font-medium text-muted-foreground">{step.label}</span>
                  {i < 2 && <span className="text-muted-foreground/30 ml-2">→</span>}
                </div>
              ))}
            </div>

            {/* Example topics */}
            <div className="space-y-2 text-left">
              <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-2 text-center">
                Try an example
              </p>
              {EXAMPLE_TOPICS.map((example, i) => (
                <button
                  key={i}
                  onClick={() => setTopic(example)}
                  className="w-full flex items-center gap-2 px-4 py-2.5 rounded-lg text-[12px] transition-all hover:scale-[1.01] bg-background border text-muted-foreground hover:text-foreground hover:border-violet-300"
                >
                  <span className="text-violet-400">→</span>
                  <span className="truncate">{example}</span>
                </button>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
