"use client";

import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { useResearchSession, ResearchAgent, ResearchEvent } from "@/lib/use-research-session";
import ReactMarkdown from "react-markdown";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Phase configuration - simplified flow
const PHASES = [
  { id: "pending", label: "Ready", icon: "○" },
  { id: "spawning", label: "Analyzing", icon: "🧠" },
  { id: "synthesizing", label: "Generating Guide", icon: "✍️" },
  { id: "researching", label: "Finding Resources", icon: "🔍" },
  { id: "complete", label: "Complete", icon: "✓" },
];

// Status colors - keeping dynamic colors as inline styles since they are computed per-status
const STATUS_CONFIG: Record<string, { bg: string; border: string; text: string; glow: string; label: string }> = {
  waiting: { bg: "rgba(148, 163, 184, 0.08)", border: "rgba(148, 163, 184, 0.2)", text: "#94A3B8", glow: "none", label: "Waiting" },
  searching: { bg: "rgba(88, 166, 255, 0.12)", border: "rgba(88, 166, 255, 0.3)", text: "#58A6FF", glow: "0 0 20px rgba(88, 166, 255, 0.2)", label: "Searching" },
  found: { bg: "rgba(74, 222, 128, 0.12)", border: "rgba(74, 222, 128, 0.3)", text: "#4ADE80", glow: "0 0 20px rgba(74, 222, 128, 0.2)", label: "Found" },
  debating: { bg: "rgba(251, 191, 36, 0.12)", border: "rgba(251, 191, 36, 0.3)", text: "#FBBF24", glow: "0 0 20px rgba(251, 191, 36, 0.2)", label: "Debating" },
  done: { bg: "rgba(74, 222, 128, 0.08)", border: "rgba(74, 222, 128, 0.2)", text: "#4ADE80", glow: "none", label: "Done" },
};

function PhaseProgress({ currentPhase }: { currentPhase: string }) {
  const currentIndex = PHASES.findIndex((p) => p.id === currentPhase);

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-2">
      {PHASES.map((phase, i) => {
        const isActive = phase.id === currentPhase;
        const isPast = i < currentIndex;

        return (
          <div key={phase.id} className="flex items-center">
            <div
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium transition-all duration-300 border",
                isActive && "scale-105",
                isActive && "bg-primary/15 border-primary/40 text-primary shadow-sm",
                isPast && "bg-success/10 border-success/20 text-success",
                !isActive && !isPast && "bg-muted/50 border-border text-muted-foreground"
              )}
            >
              <span className={isActive ? "animate-pulse" : ""}>{phase.icon}</span>
              <span className="whitespace-nowrap">{phase.label}</span>
            </div>
            {i < PHASES.length - 1 && (
              <div
                className={cn(
                  "w-4 h-[2px] mx-1",
                  isPast ? "bg-success/40" : "bg-border"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function AgentCard({
  agent,
  events,
  isExpanded,
  onToggle,
}: {
  agent: ResearchAgent;
  events: ResearchEvent[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const config = STATUS_CONFIG[agent.status] || STATUS_CONFIG.waiting;
  const agentEvents = events.filter((e) => e.agent_id === agent.id);
  const searchEvents = agentEvents.filter((e) => e.type === "agent_search_started" || e.type === "agent_search_result");
  const findings = agentEvents.filter((e) => e.type === "agent_finding");
  const debates = agentEvents.filter((e) => e.type === "debate_turn");

  return (
    <div
      className="rounded-xl overflow-hidden transition-all duration-300"
      style={{
        background: config.bg,
        border: `1px solid ${config.border}`,
        boxShadow: config.glow,
      }}
    >
      {/* Header - Always visible */}
      <button
        onClick={onToggle}
        className="w-full p-3 flex items-start gap-3 text-left hover:bg-accent/5 transition-colors"
      >
        <div
          className="text-2xl h-10 w-10 rounded-lg flex items-center justify-center bg-muted/50"
        >
          {agent.avatar}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">
              {agent.name}
            </h3>
            <Badge
              variant="secondary"
              className="text-[9px] font-mono uppercase tracking-wide"
              style={{ background: config.bg, color: config.text, border: `1px solid ${config.border}` }}
            >
              {config.label}
            </Badge>
          </div>
          <p className="text-[11px] mt-0.5 line-clamp-1 text-muted-foreground">
            {agent.expertise}
          </p>

          {/* Activity indicator */}
          {agent.status === "searching" && agent.currentQuery && (
            <div
              className="mt-2 flex items-center gap-2 text-[10px] font-mono px-2 py-1 rounded bg-muted/50"
              style={{ color: config.text }}
            >
              <span className="animate-pulse">●</span>
              <span className="truncate">{agent.currentQuery}</span>
            </div>
          )}

          {/* Stats row */}
          <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <span>🔍</span> {agent.searchCount} searches
            </span>
            <span className="flex items-center gap-1">
              <span>📄</span> {agent.resultCount} results
            </span>
            {findings.length > 0 && (
              <span className="flex items-center gap-1 text-success">
                <span>💡</span> Finding ready
              </span>
            )}
          </div>
        </div>

        {/* Expand/collapse indicator */}
        <svg
          className={cn(
            "h-4 w-4 transition-transform duration-200 text-muted-foreground",
            isExpanded && "rotate-180"
          )}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t px-3 py-3 space-y-3 bg-muted/30">
          {/* Search activity */}
          {searchEvents.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold uppercase tracking-wide mb-2 text-muted-foreground">
                Search Activity
              </h4>
              <div className="space-y-1.5">
                {searchEvents.map((e, i) => (
                  <div key={i} className="text-[11px] text-muted-foreground">
                    {e.type === "agent_search_started" ? (
                      <span className="flex items-center gap-1.5">
                        <span className="text-primary">→</span>
                        <span className="font-mono">{e.query}</span>
                      </span>
                    ) : (
                      <span className="flex items-start gap-1.5">
                        <span className="text-success">✓</span>
                        <span>
                          Found {e.result_count} results
                          {e.snippet && (
                            <span className="block mt-0.5 text-[10px] line-clamp-2 text-muted-foreground">
                              {e.snippet}
                            </span>
                          )}
                        </span>
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Finding */}
          {findings.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold uppercase tracking-wide mb-2 text-success">
                Research Finding
              </h4>
              <div className="text-xs p-2.5 rounded-lg bg-success/5 border border-success/10">
                <p className="text-muted-foreground">{findings[0].content}</p>
              </div>
            </div>
          )}

          {/* Debate contribution */}
          {debates.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold uppercase tracking-wide mb-2 text-warning">
                Debate Contribution
              </h4>
              <div className="text-xs p-2.5 rounded-lg bg-warning/5 border border-warning/10">
                <p className="text-muted-foreground">{debates[0].content}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MARKDOWN_COMPONENTS: Record<string, React.ComponentType<any>> = {
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold mt-8 mb-4 pb-2 text-foreground border-b">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-medium mt-6 mb-3 text-foreground">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="text-sm leading-relaxed mb-4 text-muted-foreground">
      {children}
    </p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-outside ml-5 mb-4 space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-outside ml-5 mb-4 space-y-1">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-sm leading-relaxed text-muted-foreground">
      {children}
    </li>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="text-muted-foreground">{children}</em>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline decoration-1 underline-offset-2 hover:decoration-2 text-primary"
    >
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-4">
      <table className="w-full text-sm border-collapse">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-muted">{children}</thead>
  ),
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => (
    <tr className="border-b">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left text-xs font-semibold text-foreground border-b-2">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-sm text-muted-foreground">
      {children}
    </td>
  ),
  code: ({ children, className }) => {
    if (!className) {
      return (
        <code className="px-1 py-0.5 rounded text-xs font-mono bg-muted text-foreground">
          {children}
        </code>
      );
    }
    return (
      <pre className="p-4 rounded-lg overflow-x-auto text-xs my-4 bg-background">
        <code className="font-mono text-muted-foreground">{children}</code>
      </pre>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 pl-4 my-4 italic border-border text-muted-foreground">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-6 border-border" />,
};

function SynthesisDisplay({ synthesis, isStreaming }: { synthesis: string; isStreaming: boolean }) {
  // Debounce markdown rendering while streaming to avoid re-parsing on every chunk
  const [rendered, setRendered] = useState(synthesis);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (!isStreaming) {
      // Not streaming — render immediately
      setRendered(synthesis);
      return;
    }
    // While streaming, debounce to render at most every 300ms
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setRendered(synthesis), 300);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [synthesis, isStreaming]);

  return (
    <article className="prose-wiki max-w-none">
      <ReactMarkdown components={MARKDOWN_COMPONENTS}>
        {rendered}
      </ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-0.5 animate-pulse rounded-sm bg-primary" />
      )}
    </article>
  );
}

function ElapsedTime({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  return (
    <span className="font-mono">
      {mins > 0 ? `${mins}m ` : ""}
      {secs}s
    </span>
  );
}

export default function ResearchPage() {
  const {
    session,
    agents,
    events,
    synthesis,
    error,
    connected,
    startSession,
    stopSession,
    reset,
  } = useResearchSession();

  const [topic, setTopic] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<"agents" | "output">("agents");
  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledRef = useRef(false);

  const toggleAgent = (id: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleStart = async () => {
    if (!topic.trim() || isStarting) return;
    setIsStarting(true);
    setExpandedAgents(new Set());
    await startSession(topic.trim());
    setIsStarting(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleStart();
    }
  };

  const isRunning = session ? !["complete", "cancelled", "error"].includes(session.status) : false;

  // Auto-expand agents when they start searching
  useEffect(() => {
    agents.forEach((agent) => {
      if (agent.status === "searching" && !expandedAgents.has(agent.id)) {
        setExpandedAgents((prev) => new Set([...prev, agent.id]));
      }
    });
  }, [agents, expandedAgents]);

  // Switch to output tab when synthesis starts streaming in
  useEffect(() => {
    if (synthesis) {
      setActiveTab("output");
    }
  }, [synthesis]);

  // Auto-scroll to bottom while streaming (unless user scrolled up)
  useEffect(() => {
    if (!synthesis || !scrollRef.current || userScrolledRef.current) return;
    const el = scrollRef.current;
    el.scrollTop = el.scrollHeight;
  }, [synthesis]);

  // Detect when user scrolls away from bottom to pause auto-scroll
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    userScrolledRef.current = !nearBottom;
  }, []);

  // Reset scroll tracking on new session
  useEffect(() => {
    userScrolledRef.current = false;
  }, [session?.id]);

  const isSynthesisStreaming = isRunning && !!synthesis;

  return (
    <div className="h-full flex flex-col p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary/80 to-primary shadow-lg">
            <span className="text-2xl brightness-200">
              🔬
            </span>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              Live Research Lab
            </h1>
            <p className="text-sm text-muted-foreground">
              Parallel agent research with real-time analysis
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {session && (
            <>
              <Card className="flex items-center gap-2 px-3 py-1.5 text-xs">
                <div
                  className={cn(
                    "h-2 w-2 rounded-full",
                    connected ? "bg-success" : "bg-destructive"
                  )}
                  style={{
                    boxShadow: connected ? "0 0 8px rgba(74, 222, 128, 0.5)" : "none",
                  }}
                />
                <span className="text-muted-foreground">
                  {isRunning ? (
                    <ElapsedTime startedAt={session.startedAt} />
                  ) : (
                    session.status
                  )}
                </span>
              </Card>

              {isRunning ? (
                <Button
                  onClick={stopSession}
                  variant="outline"
                  className="text-sm font-medium text-destructive border-destructive/30 bg-destructive/10 hover:bg-destructive/20 hover:scale-105 transition-all"
                >
                  Stop Research
                </Button>
              ) : (
                <Button
                  onClick={reset}
                  variant="outline"
                  className="text-sm font-medium hover:scale-105 transition-all"
                >
                  New Research
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Topic Input */}
      <Card className="p-5 shrink-0">
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="text-xs font-semibold uppercase tracking-wide mb-2 block text-muted-foreground">
              Research Topic
            </label>
            <Input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="What would you like to research? (e.g., Best practices for building reaction wheels for small satellites)"
              disabled={isRunning}
              className={cn(
                "px-4 py-3 rounded-lg text-sm",
                isRunning && "opacity-50"
              )}
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={handleStart}
              disabled={!topic.trim() || isStarting || isRunning}
              className="px-6 py-3 rounded-lg text-sm font-semibold hover:scale-105 disabled:hover:scale-100 transition-all"
            >
              {isStarting ? "Starting..." : "Start Research"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Phase Progress + Intent Badge */}
      {session && (
        <Card className="px-5 py-3 shrink-0">
          <div className="flex items-center justify-between gap-4 mb-2">
            <PhaseProgress currentPhase={session.status} />
            {session.intent && (
              <div className="flex items-center gap-2 shrink-0">
                <Badge
                  variant={session.intent === "build" ? "success" : "info"}
                  className="text-[10px] font-semibold uppercase tracking-wide"
                >
                  {session.intent === "build" ? "🛠️ BUILD" : "📊 ANALYZE"}
                </Badge>
                {session.domain && session.domain !== "general" && (
                  <Badge variant="secondary" className="text-[10px]">
                    {session.domain}
                  </Badge>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      {error && (
        <div className="rounded-xl p-4 shrink-0 bg-destructive/10 border border-destructive/20 text-destructive">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Main Content */}
      {session && (
        <div className="flex-1 min-h-0 flex flex-col">
          {/* Tab switcher */}
          <div className="flex gap-2 mb-4 shrink-0">
            <button
              onClick={() => setActiveTab("agents")}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-all border",
                activeTab === "agents"
                  ? "bg-primary/15 text-primary border-primary/30"
                  : "text-muted-foreground border-transparent hover:text-foreground"
              )}
            >
              🤖 Research Agents ({agents.length})
            </button>
            <button
              onClick={() => setActiveTab("output")}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-all border",
                activeTab === "output"
                  ? "bg-primary/15 text-primary border-primary/30"
                  : "text-muted-foreground border-transparent hover:text-foreground"
              )}
            >
              📊 Research Output {synthesis ? "✓" : ""}
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 min-h-0 overflow-auto" ref={scrollRef} onScroll={handleScroll}>
            {activeTab === "agents" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {agents.length === 0 ? (
                  <Card className="col-span-full flex items-center justify-center h-48">
                    <div className="text-center">
                      <div className="text-3xl mb-2 animate-pulse">🧬</div>
                      <p className="text-sm text-muted-foreground">
                        Spawning research agents...
                      </p>
                    </div>
                  </Card>
                ) : (
                  agents.map((agent) => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      events={events}
                      isExpanded={expandedAgents.has(agent.id)}
                      onToggle={() => toggleAgent(agent.id)}
                    />
                  ))
                )}
              </div>
            )}

            {activeTab === "output" && (
              <Card>
                {!synthesis ? (
                  <div className="flex items-center justify-center h-48">
                    <div className="text-center">
                      <div className="text-3xl mb-2">
                        {session.status === "synthesizing" ? (
                          <span className="animate-pulse">⬡</span>
                        ) : (
                          "📊"
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {session.status === "synthesizing"
                          ? "Synthesizing research findings..."
                          : "Research output will appear here after synthesis"}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="p-6 lg:p-8">
                    {/* Document header */}
                    <header className="mb-6 pb-4 border-b">
                      <h1 className="text-xl font-bold mb-1 text-foreground">
                        {session.topic}
                      </h1>
                      <p className="text-xs text-muted-foreground">
                        Research synthesis • {agents.length} agents • {new Date().toLocaleDateString()}
                      </p>
                    </header>
                    <SynthesisDisplay synthesis={synthesis} isStreaming={isSynthesisStreaming} />
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!session && (
        <Card className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-lg px-8">
            <div className="inline-flex h-20 w-20 items-center justify-center rounded-2xl mb-6 bg-primary/10 border border-primary/30 shadow-lg">
              <span className="text-4xl">🔬</span>
            </div>
            <h2 className="text-xl font-bold mb-3 text-foreground">
              Launch a Research Session
            </h2>
            <p className="text-sm mb-6 text-muted-foreground">
              Enter a topic to spawn specialized AI agents that research in parallel, debate findings, and synthesize actionable insights with cited sources.
            </p>

            <div className="grid grid-cols-1 gap-2 text-left">
              {[
                "How to build reaction wheels for small satellites using BLDC motors",
                "Build an ESP32 based IoT sensor with LoRa connectivity",
                "Compare LangGraph vs CrewAI vs AutoGen for AI agent development",
              ].map((example, i) => (
                <button
                  key={i}
                  onClick={() => setTopic(example)}
                  className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm transition-all hover:scale-[1.02] bg-background border text-muted-foreground hover:text-foreground"
                >
                  <span className="text-muted-foreground">→</span>
                  {example}
                </button>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
