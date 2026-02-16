"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { LeetCodeProgress, PrepMaterial, PrepMaterialType } from "@/lib/types";
import { BuilderProgress } from "@/components/timeline/builder-progress";
import type { BuilderInfo } from "@/lib/use-timeline-events";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

interface DailyProblem {
  id: number;
  title: string;
  difficulty: string;
  topic: string;
}

interface DiscoveryResult {
  material_id: number;
  date: string;
  problems: { title: string; difficulty: string; topics: string[]; url: string; summary: string }[];
  tutorials: { title: string; url: string; source: string; summary: string }[];
  blog_posts: { title: string; url: string; source: string; summary: string }[];
}

const MATERIAL_TYPE_LABELS: Record<PrepMaterialType, { label: string; badgeVariant: "success" | "info" | "warning" | "destructive" | "secondary"; icon: string }> = {
  interview: { label: "Strategist Intel", badgeVariant: "success", icon: "\u265F\uFE0F" },
  system_design: { label: "Architect Brief", badgeVariant: "info", icon: "\u25B3" },
  leetcode: { label: "Coding Challenge", badgeVariant: "warning", icon: "\u25C8" },
  company_research: { label: "Oracle Report", badgeVariant: "secondary", icon: "\u25C9" },
  general: { label: "Nexus Guide", badgeVariant: "secondary", icon: "\u2B21" },
  tutorial: { label: "Field Manual", badgeVariant: "info", icon: "\uD83D\uDCCB" },
};

const DIFFICULTY_VARIANT: Record<string, "success" | "warning" | "destructive"> = {
  easy: "success",
  medium: "warning",
  hard: "destructive",
};

const MASTERY_COLORS = [
  { bar: "bg-gradient-to-r from-yellow-400 to-yellow-300" },
  { bar: "bg-gradient-to-r from-blue-400 to-blue-300" },
  { bar: "bg-gradient-to-r from-green-400 to-green-300" },
  { bar: "bg-gradient-to-r from-purple-400 to-purple-300" },
  { bar: "bg-gradient-to-r from-pink-400 to-pink-300" },
  { bar: "bg-gradient-to-r from-orange-400 to-orange-300" },
];

export default function PrepPage() {
  const router = useRouter();
  const [progress, setProgress] = useState<LeetCodeProgress | null>(null);
  const [dailyProblems, setDailyProblems] = useState<DailyProblem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [activeProblem, setActiveProblem] = useState<DailyProblem | null>(null);
  const [materials, setMaterials] = useState<PrepMaterial[]>([]);
  const [materialFilter, setMaterialFilter] = useState<PrepMaterialType | "all">("all");
  const [expandedMaterial, setExpandedMaterial] = useState<number | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [activeDiscoveryIdx, setActiveDiscoveryIdx] = useState<number | null>(null);
  const [resourceTab, setResourceTab] = useState<"tutorials" | "blogs">("tutorials");

  // Generate field manual state
  const FOCUS_OPTIONS = [
    { value: "", label: "Auto", description: "Let agents decide" },
    { value: "Interview prep \u2014 focus on fundamentals, common questions, and how to explain concepts clearly to an interviewer", label: "Interview Prep", description: "Fundamentals & how to explain" },
    { value: "Deep dive \u2014 thorough technical reference with implementation details, tradeoffs, and edge cases", label: "Deep Dive", description: "In-depth technical reference" },
    { value: "Quick overview \u2014 concise summary hitting key concepts, when to use, pros and cons", label: "Quick Overview", description: "Concise key concepts" },
    { value: "System design \u2014 focus on architecture patterns, scalability, real-world usage at scale, and design tradeoffs", label: "System Design", description: "Architecture & scalability" },
  ] as const;
  const [generateTopic, setGenerateTopic] = useState("");
  const [generateFocus, setGenerateFocus] = useState("");
  const [generating, setGenerating] = useState(false);
  const [virtualPostId, setVirtualPostId] = useState<number | null>(null);
  const [builders, setBuilders] = useState<BuilderInfo[]>([]);
  const [swarmPhase, setSwarmPhase] = useState<string>(""); // "research" | "debate" | "synthesis" | "building" | ""
  const [swarmAgents, setSwarmAgents] = useState<Record<string, { name: string; thinking: boolean }>>({});
  const sseRef = useRef<EventSource | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/ai/leetcode/progress").then((r) => r.json()),
      fetch("/api/ai/leetcode/daily").then((r) => r.json()),
      fetch("/api/ai/prep/materials").then((r) => r.json()),
    ])
      .then(([prog, daily, mats]) => {
        if (prog) setProgress(prog);
        if (daily?.problems) setDailyProblems(daily.problems);
        if (mats?.materials) setMaterials(mats.materials);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleDeleteMaterial(id: number) {
    try {
      await fetch(`/api/ai/prep/materials/${id}`, { method: "DELETE" });
      setMaterials((prev) => prev.filter((m) => m.id !== id));
    } catch {}
  }

  async function handleDiscover() {
    setDiscovering(true);
    try {
      const res = await fetch("/api/ai/prep/discover", { method: "POST" });
      if (!res.ok) throw new Error("Discovery failed");
      const data: DiscoveryResult = await res.json();
      setDiscovery(data);
      // Refresh materials list so the new one appears
      const matsRes = await fetch("/api/ai/prep/materials");
      const mats = await matsRes.json();
      if (mats?.materials) setMaterials(mats.materials);
    } catch {
      // silently fail
    } finally {
      setDiscovering(false);
    }
  }

  async function handleGenerate() {
    const topic = generateTopic.trim();
    if (!topic || topic.length < 3 || generating) return;

    setGenerating(true);
    setBuilders([]);
    setSwarmPhase("");
    setSwarmAgents({});
    try {
      const res = await fetch("/api/ai/prep/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, focus: generateFocus }),
      });
      if (!res.ok) throw new Error("Generation failed");
      const data = await res.json();
      setVirtualPostId(data.virtual_post_id);
    } catch {
      setGenerating(false);
    }
  }

  // SSE listener for builder progress when generating
  useEffect(() => {
    if (!virtualPostId) return;

    let closed = false;
    const es = new EventSource("/api/ai/timeline/stream");
    sseRef.current = es;

    es.onmessage = async (event) => {
      if (closed) return;
      try {
        const data = JSON.parse(event.data);

        // Skip the big initial timeline_state dump immediately
        if (data.type === "timeline_state" || data.type === "heartbeat") return;

        const postId = data.post_id;

        // Filter events to our virtual post
        if (postId !== virtualPostId) return;

        // --- Swarm progress events (research phase) ---
        if (data.type === "swarm_started") {
          setSwarmPhase("research");
          const agents: Record<string, { name: string; thinking: boolean }> = {};
          if (data.dynamic_agents) {
            for (const [id, info] of Object.entries(data.dynamic_agents as Record<string, { display_name: string }>)) {
              agents[id] = { name: info.display_name, thinking: false };
            }
          }
          setSwarmAgents(agents);
          return;
        }
        if (data.type === "agent_requested") {
          setSwarmAgents((prev) => ({
            ...prev,
            [data.agent_id]: { name: data.agent_name || data.agent_id, thinking: false },
          }));
          return;
        }
        if (data.type === "agent_thinking") {
          setSwarmAgents((prev) => {
            const agent = prev[data.agent];
            if (!agent) return prev;
            return { ...prev, [data.agent]: { ...agent, thinking: true } };
          });
          return;
        }
        if (data.type === "swarm_phase") {
          setSwarmPhase(data.phase || "research");
          setSwarmAgents((prev) => {
            const next: typeof prev = {};
            for (const [id, a] of Object.entries(prev)) next[id] = { ...a, thinking: false };
            return next;
          });
          return;
        }
        if (data.type === "swarm_complete") {
          setSwarmPhase("building");
          return;
        }

        // --- Builder progress events ---
        if (data.type === "builder_dispatched") {
          setBuilders((prev) => [
            ...prev.filter((b) => b.builderId !== data.builder_id),
            {
              builderId: data.builder_id,
              postId,
              title: data.title || "Generating...",
              agentName: data.agent_name || "builder",
              percent: 0,
              stage: "queued",
              materialId: null,
              complete: false,
            },
          ]);
        } else if (data.type === "builder_progress") {
          setBuilders((prev) =>
            prev.map((b) =>
              b.builderId === data.builder_id
                ? { ...b, percent: data.percent ?? b.percent, stage: data.stage ?? b.stage, title: data.title ?? b.title }
                : b,
            ),
          );
        } else if (data.type === "builder_complete") {
          setBuilders((prev) =>
            prev.map((b) =>
              b.builderId === data.builder_id
                ? { ...b, percent: 100, stage: "complete", complete: true, materialId: data.material_id ?? null }
                : b,
            ),
          );
          // Refresh materials list
          try {
            const matsRes = await fetch("/api/ai/prep/materials");
            const mats = await matsRes.json();
            if (mats?.materials) setMaterials(mats.materials);
          } catch {}
          // Done generating
          closed = true;
          es.close();
          setGenerating(false);
          setVirtualPostId(null);
          setGenerateTopic("");
          setSwarmPhase("");
          setSwarmAgents({});
        }
      } catch {}
    };

    es.onerror = () => {
      // Don't kill state on transient SSE errors -- EventSource auto-reconnects.
      // Only bail if the connection is fully dead (CLOSED).
      if (es.readyState === EventSource.CLOSED) {
        closed = true;
        setGenerating(false);
        setVirtualPostId(null);
        setSwarmPhase("");
        setSwarmAgents({});
      }
    };

    return () => {
      closed = true;
      es.close();
      sseRef.current = null;
    };
  }, [virtualPostId]);

  function handleStartSession() {
    setSessionLoading(true);
    router.push("/ai?source=prep");
  }

  function handleSolve(problem: DailyProblem) {
    router.push(`/ai?source=prep&message=${encodeURIComponent(`I want to solve LeetCode #${problem.id} "${problem.title}" (${problem.difficulty}, ${problem.topic}). Guide me through it.`)}`);
  }

  function handleGetHint(problem: DailyProblem) {
    router.push(`/ai?source=prep&message=${encodeURIComponent(`Give me a hint for LeetCode #${problem.id} "${problem.title}". Don't give the solution, just point me in the right direction.`)}`);
  }

  function handleExplain(problem: DailyProblem) {
    router.push(`/ai?source=prep&message=${encodeURIComponent(`Explain the optimal solution for LeetCode #${problem.id} "${problem.title}". Walk me through the approach, pattern, and complexity.`)}`);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <svg className="h-6 w-6 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  const mastery = progress?.mastery || [];

  const stats = [
    { label: "Decoded", value: progress?.total_solved || 0, color: "text-green-400", icon: "\u25C8" },
    { label: "Attempted", value: progress?.total_attempted || 0, color: "text-blue-400", icon: "\u25C7" },
    { label: "Streak", value: progress?.streak || 0, color: "text-yellow-400", icon: "\u26A1" },
    { label: "Patterns", value: mastery.length, color: "text-purple-400", icon: "\u25B3" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="animate-fade-in-up flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl flex items-center justify-center text-lg bg-gradient-to-br from-orange-500/15 to-purple-500/12 border border-orange-500/20">
            {"\u25C8"}
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">Interview Preparation</h1>
            <p className="text-[11px] data-mono text-muted-foreground/70">
              Algorithms &middot; System Design &middot; Interview Intel
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleDiscover}
            disabled={discovering}
            className="rounded-xl px-5 py-2.5 text-sm font-semibold text-warning border-warning/30"
          >
            {discovering ? (
              <span className="flex items-center gap-2">
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Searching...
              </span>
            ) : "\u26A1 Scout Resources"}
          </Button>
          <Button
            onClick={handleStartSession}
            disabled={sessionLoading}
            className="rounded-xl px-5 py-2.5 text-sm font-semibold"
          >
            {sessionLoading ? (
              <span className="flex items-center gap-2">
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Initializing...
              </span>
            ) : "\u2B21 Enter Arena"}
          </Button>
        </div>
      </div>

      {/* Generate Field Manual */}
      <Card className="p-4 animate-fade-in-up [animation-delay:0.05s]">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sky-400">&#x1F4CB;</span>
            <h3 className="text-[13px] font-semibold text-foreground">
              Generate Study Guide
            </h3>
            <span className="text-[10px] text-muted-foreground/70">
              AI-researched tutorial on any topic
            </span>
          </div>
          {/* Focus selector */}
          <div className="flex gap-1.5 mb-2 flex-wrap">
            {FOCUS_OPTIONS.map((opt) => {
              const isActive = generateFocus === opt.value;
              return (
                <Badge
                  key={opt.label}
                  variant={isActive ? "info" : "secondary"}
                  className={cn(
                    "cursor-pointer text-[10px] transition-all duration-200",
                    generating && "opacity-50 pointer-events-none",
                    isActive && "border border-sky-400/30",
                  )}
                  onClick={() => !generating && setGenerateFocus(opt.value)}
                  title={opt.description}
                >
                  {opt.label}
                </Badge>
              );
            })}
          </div>
          <div className="flex gap-2">
            <Input
              type="text"
              value={generateTopic}
              onChange={(e) => setGenerateTopic(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleGenerate(); }}
              placeholder='e.g. "binary search trees", "system design load balancers"'
              disabled={generating}
              className="flex-1 rounded-xl text-[12px]"
              maxLength={500}
            />
            <Button
              onClick={handleGenerate}
              disabled={generating || generateTopic.trim().length < 3}
              className={cn("rounded-xl px-5 py-2 text-[12px] font-semibold shrink-0", generating && "bg-sky-400/10 border-sky-400/30")}
            >
              {generating ? (
                <span className="flex items-center gap-2">
                  <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Generating...
                </span>
              ) : "Generate"}
            </Button>
          </div>
          {/* Swarm progress (research -> debate -> synthesis) */}
          {generating && swarmPhase && builders.length === 0 && (
            <div className="mt-3 rounded-xl px-3 py-2.5 animate-fade-in bg-sky-400/5 border border-sky-400/15">
              <div className="flex items-center gap-2 mb-2">
                <svg className="h-3.5 w-3.5 animate-spin shrink-0 text-sky-400" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="text-[12px] font-semibold text-sky-400">
                  {swarmPhase === "research" && "Researching..."}
                  {swarmPhase === "debate" && "Agents debating findings..."}
                  {swarmPhase === "synthesis" && "Synthesizing consensus..."}
                  {swarmPhase === "building" && "Preparing to build tutorial..."}
                </span>
              </div>
              {/* Phase steps */}
              <div className="flex items-center gap-1 mb-2">
                {(["research", "debate", "synthesis", "building"] as const).map((phase) => {
                  const phases = ["research", "debate", "synthesis", "building"];
                  const currentIdx = phases.indexOf(swarmPhase);
                  const phaseIdx = phases.indexOf(phase);
                  const isDone = phaseIdx < currentIdx;
                  const isCurrent = phase === swarmPhase;
                  return (
                    <div key={phase} className="flex items-center gap-1">
                      {phaseIdx > 0 && (
                        <div className={cn("w-4 h-px", isDone ? "bg-sky-400/50" : "bg-sky-400/15")} />
                      )}
                      <span
                        className={cn(
                          "text-[9px] font-medium px-1.5 py-0.5 rounded",
                          isCurrent && "bg-sky-400/15 text-sky-400",
                          isDone && "bg-sky-400/8 text-sky-400/60",
                          !isCurrent && !isDone && "text-sky-400/30",
                        )}
                      >
                        {phase === "research" ? "Research" : phase === "debate" ? "Debate" : phase === "synthesis" ? "Synthesis" : "Build"}
                      </span>
                    </div>
                  );
                })}
              </div>
              {/* Active agents */}
              {Object.keys(swarmAgents).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(swarmAgents).map(([id, agent]) => (
                    <span
                      key={id}
                      className={cn(
                        "text-[10px] font-medium px-2 py-0.5 rounded-lg",
                        agent.thinking ? "bg-sky-400/12 text-sky-400" : "bg-sky-400/6 text-sky-400/50",
                      )}
                    >
                      {agent.thinking && (
                        <span className="inline-block w-1.5 h-1.5 rounded-full mr-1 animate-pulse bg-sky-400" />
                      )}
                      {agent.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          <BuilderProgress builders={builders} />
        </div>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 stagger">
        {stats.map((stat) => (
          <Card key={stat.label} className="p-4 text-center">
            <div className="relative z-10">
              <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
                <span className={cn("data-mono text-lg font-bold", stat.color)}>{stat.value}</span>
              </div>
              <p className="text-[11px] font-medium text-muted-foreground/70">{stat.label}</p>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6 [animation-delay:0.15s]">
        {/* Today's Problems */}
        <Card className="p-4 animate-fade-in-up [animation-delay:0.2s]">
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <h3 className="text-[13px] font-semibold text-foreground">{"\u25C8"} Daily Challenges</h3>
                {discovery && (
                  <Badge variant="warning" className="text-[9px]">
                    AI Picks
                  </Badge>
                )}
              </div>
              <span className="text-xs text-muted-foreground">
                {discovery ? discovery.problems.length : dailyProblems.length} queued
              </span>
            </div>

            {/* Discovery problems */}
            {discovery ? (
              discovery.problems.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-[12px] text-muted-foreground">No problems found</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {discovery.problems.map((p, i) => {
                    const diffVariant = DIFFICULTY_VARIANT[p.difficulty] || "warning";
                    const isActive = activeDiscoveryIdx === i;
                    return (
                      <div key={i}>
                        <div
                          className={cn(
                            "flex items-center justify-between rounded-xl px-3 py-2.5 transition-all duration-200 cursor-pointer",
                            isActive ? "bg-accent" : "bg-muted hover:bg-accent",
                          )}
                          onClick={() => setActiveDiscoveryIdx(isActive ? null : i)}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-[12px] font-medium truncate text-foreground">
                              {p.title}
                            </p>
                            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                              {p.topics?.slice(0, 3).map((t) => (
                                <span key={t} className="text-[10px] capitalize text-muted-foreground/70">{t}</span>
                              ))}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <Badge variant={diffVariant} className="capitalize">
                              {p.difficulty}
                            </Badge>
                            <a
                              href={p.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[10px] font-medium text-primary"
                              onClick={(e) => e.stopPropagation()}
                            >
                              Open
                            </a>
                          </div>
                        </div>
                        {isActive && (
                          <div className="px-3 py-2 animate-fade-in-up">
                            <p className="text-[11px] leading-relaxed mb-2 text-muted-foreground">
                              {p.summary}
                            </p>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={() => router.push(`/ai?source=prep&message=${encodeURIComponent(`I want to solve "${p.title}" (${p.difficulty}). ${p.summary} Guide me through it.`)}`)}
                                className="rounded-lg px-3 py-1.5 text-[11px] font-semibold h-auto"
                              >
                                Solve with AI
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => router.push(`/ai?source=prep&message=${encodeURIComponent(`Give me a hint for "${p.title}" (${p.difficulty}). Don't give the full solution.`)}`)}
                                className="rounded-lg px-3 py-1.5 text-[11px] font-semibold text-warning h-auto"
                              >
                                Get Hint
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                asChild
                                className="rounded-lg px-3 py-1.5 text-[11px] font-semibold text-primary h-auto"
                              >
                                <a
                                  href={p.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  View Problem
                                </a>
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )
            ) : dailyProblems.length === 0 ? (
              <div className="text-center py-8">
                <svg
                  className="mx-auto h-10 w-10 mb-2 text-muted-foreground/30"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M14.25 9.75L16.5 12l-2.25 2.25m-4.5 0L7.5 12l2.25-2.25M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z"
                  />
                </svg>
                <p className="text-[12px] text-muted-foreground">No challenges queued</p>
                <p className="text-[10px] mt-0.5 text-muted-foreground/70">
                  Click &quot;\u26A1 Scout Resources&quot; to discover problems
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {dailyProblems.map((p, i) => {
                  const diffVariant = DIFFICULTY_VARIANT[p.difficulty] || "warning";
                  const isActive = activeProblem?.id === p.id;
                  return (
                    <div key={p.id}>
                      <div
                        className={cn(
                          "flex items-center justify-between rounded-xl px-3 py-2.5 transition-all duration-200 cursor-pointer",
                          isActive ? "bg-accent" : "bg-muted hover:bg-accent",
                        )}
                        onClick={() => setActiveProblem(isActive ? null : p)}
                      >
                        <div>
                          <p className="text-[12px] font-medium text-foreground">
                            <span className="data-mono text-muted-foreground/70">#{p.id}</span>
                            {" "}{p.title}
                          </p>
                          <p className="text-[10px] capitalize text-muted-foreground/70">{p.topic}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={diffVariant} className="capitalize">
                            {p.difficulty}
                          </Badge>
                          <a
                            href={`https://leetcode.com/problems/`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] font-medium text-primary"
                            onClick={(e) => e.stopPropagation()}
                          >
                            LC
                          </a>
                        </div>
                      </div>
                      {isActive && (
                        <div className="flex gap-2 px-3 py-2 animate-fade-in-up">
                          <Button
                            size="sm"
                            onClick={() => handleSolve(p)}
                            className="rounded-lg px-3 py-1.5 text-[11px] font-semibold h-auto"
                          >
                            Solve
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleGetHint(p)}
                            className="rounded-lg px-3 py-1.5 text-[11px] font-semibold text-warning h-auto"
                          >
                            Get Hint
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleExplain(p)}
                            className="rounded-lg px-3 py-1.5 text-[11px] font-semibold text-primary h-auto"
                          >
                            Explain
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Card>

        {/* Right column: Resources (when discovery) or Skill Mastery */}
        <Card className="p-4 animate-fade-in-up [animation-delay:0.25s]">
          <div className="relative z-10">
            {discovery ? (
              <>
                {/* Tab header */}
                <div className="flex items-center gap-1 mb-3">
                  <button
                    onClick={() => setResourceTab("tutorials")}
                    className={cn(
                      "text-[13px] font-semibold px-2 py-1 rounded-lg transition-colors",
                      resourceTab === "tutorials" ? "text-foreground bg-muted" : "text-muted-foreground/70",
                    )}
                  >
                    Tutorials ({discovery.tutorials.length})
                  </button>
                  <button
                    onClick={() => setResourceTab("blogs")}
                    className={cn(
                      "text-[13px] font-semibold px-2 py-1 rounded-lg transition-colors",
                      resourceTab === "blogs" ? "text-foreground bg-muted" : "text-muted-foreground/70",
                    )}
                  >
                    Blog Posts ({discovery.blog_posts.length})
                  </button>
                  <Badge variant="warning" className="text-[9px] ml-auto">
                    AI Picks
                  </Badge>
                </div>

                {/* Tutorials tab */}
                {resourceTab === "tutorials" && (
                  <div className="space-y-2">
                    {discovery.tutorials.length === 0 ? (
                      <p className="text-[12px] text-center py-6 text-muted-foreground/70">No tutorials found</p>
                    ) : discovery.tutorials.map((t, i) => (
                      <a
                        key={i}
                        href={t.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block rounded-xl px-3 py-2.5 transition-all duration-200 bg-muted hover:bg-accent"
                      >
                        <p className="text-[12px] font-medium mb-0.5 text-foreground">
                          {t.title}
                        </p>
                        <p className="text-[11px] leading-relaxed mb-1 text-muted-foreground">
                          {t.summary}
                        </p>
                        <span className="text-[10px] text-primary">
                          {t.source || new URL(t.url).hostname}
                        </span>
                      </a>
                    ))}
                  </div>
                )}

                {/* Blog posts tab */}
                {resourceTab === "blogs" && (
                  <div className="space-y-2">
                    {discovery.blog_posts.length === 0 ? (
                      <p className="text-[12px] text-center py-6 text-muted-foreground/70">No blog posts found</p>
                    ) : discovery.blog_posts.map((b, i) => (
                      <a
                        key={i}
                        href={b.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block rounded-xl px-3 py-2.5 transition-all duration-200 bg-muted hover:bg-accent"
                      >
                        <p className="text-[12px] font-medium mb-0.5 text-foreground">
                          {b.title}
                        </p>
                        <p className="text-[11px] leading-relaxed mb-1 text-muted-foreground">
                          {b.summary}
                        </p>
                        <span className="text-[10px] text-primary">
                          {b.source || new URL(b.url).hostname}
                        </span>
                      </a>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-[13px] font-semibold text-foreground">{"\u25B3"} Pattern Mastery</h3>
                  <span className="text-xs text-muted-foreground">{mastery.length} topics</span>
                </div>
                {mastery.length === 0 ? (
                  <div className="text-center py-8">
                    <svg
                      className="mx-auto h-10 w-10 mb-2 text-muted-foreground/30"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1}
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
                      />
                    </svg>
                    <p className="text-[12px] text-muted-foreground">No patterns decoded yet</p>
                    <p className="text-[10px] mt-0.5 text-muted-foreground/70">
                      Solve challenges to build your pattern mastery profile
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {mastery.map((m, i) => {
                      const colorSet = MASTERY_COLORS[i % MASTERY_COLORS.length];
                      return (
                        <div key={m.topic}>
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-[12px] font-medium capitalize text-muted-foreground">{m.topic}</span>
                            <span className="data-mono text-[10px] text-muted-foreground/70">
                              {m.problems_solved}/{m.problems_attempted} &middot; {m.level}%
                            </span>
                          </div>
                          <div className="h-2 rounded-full overflow-hidden bg-muted">
                            <div
                              className={cn("h-full rounded-full transition-all duration-700", colorSet.bar)}
                              style={{ width: `${m.level}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        </Card>
      </div>

      {/* Saved Prep Materials */}
      <div className="animate-fade-in-up [animation-delay:0.3s]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[15px] font-semibold text-foreground">{"\u25C9"} Knowledge Base</h2>
          <span className="text-xs text-muted-foreground">{materials.length} saved</span>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {(["all", "interview", "system_design", "leetcode", "company_research", "general", "tutorial"] as const).map((type) => {
            const isActive = materialFilter === type;
            const typeInfo = type === "all"
              ? { label: "All", badgeVariant: "secondary" as const }
              : MATERIAL_TYPE_LABELS[type];
            const count = type === "all"
              ? materials.length
              : materials.filter((m) => m.material_type === type).length;
            return (
              <Badge
                key={type}
                variant={isActive ? typeInfo.badgeVariant : "secondary"}
                className={cn(
                  "cursor-pointer transition-all duration-200",
                  isActive && "ring-1 ring-current",
                )}
                onClick={() => setMaterialFilter(type)}
              >
                {typeInfo.label} ({count})
              </Badge>
            );
          })}
        </div>

        {/* Material cards */}
        {materials.length === 0 ? (
          <Card className="p-8 text-center">
            <div className="relative z-10">
              <svg
                className="mx-auto h-10 w-10 mb-2 text-muted-foreground/30"
                fill="none"
                stroke="currentColor"
                strokeWidth={1}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                />
              </svg>
              <p className="text-[12px] text-muted-foreground">No prep materials yet</p>
              <p className="text-[10px] mt-0.5 text-muted-foreground/70">
                Start a session to generate interview prep, study plans, and more
              </p>
            </div>
          </Card>
        ) : (
          <div className="space-y-2">
            {materials
              .filter((m) => materialFilter === "all" || m.material_type === materialFilter)
              .map((m) => {
                const typeInfo = MATERIAL_TYPE_LABELS[m.material_type] || MATERIAL_TYPE_LABELS.general;
                const isExpanded = expandedMaterial === m.id;
                const resourceCount = Array.isArray(m.resources) ? m.resources.length : 0;

                return (
                  <Card key={m.id} className="overflow-hidden">
                    <button
                      onClick={() => setExpandedMaterial(isExpanded ? null : m.id)}
                      className="relative z-10 flex w-full items-center justify-between p-4 text-left transition-colors duration-200 hover:bg-accent"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <Badge variant={typeInfo.badgeVariant} className="shrink-0 flex items-center gap-1">
                          <span className="text-[9px]">{typeInfo.icon}</span>
                          {typeInfo.label}
                        </Badge>
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium truncate text-foreground">
                            {m.title}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            {m.company && (
                              <span className="text-[10px] font-medium text-primary">
                                {m.company}
                              </span>
                            )}
                            {m.role && (
                              <span className="text-[10px] text-muted-foreground/70">
                                {m.role}
                              </span>
                            )}
                            {m.scheduled_date && (
                              <Badge variant="warning" className="text-[9px]">
                                {new Date(m.scheduled_date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                              </Badge>
                            )}
                            {resourceCount > 0 && (
                              <span className="text-[10px] text-muted-foreground/70">
                                {resourceCount} resource{resourceCount !== 1 ? "s" : ""}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] text-muted-foreground/70">
                          {new Date(m.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </span>
                        <svg
                          className={cn("h-4 w-4 transition-transform duration-200 text-muted-foreground", isExpanded && "rotate-180")}
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="relative z-10 p-4 animate-fade-in border-t">
                        {/* Content preview */}
                        <div className="text-[12px] leading-relaxed mb-3 text-muted-foreground">
                          {typeof m.content === "object" && m.content !== null ? (
                            <pre className="whitespace-pre-wrap font-sans text-[11px] text-muted-foreground">
                              {JSON.stringify(m.content, null, 2).slice(0, 500)}
                              {JSON.stringify(m.content, null, 2).length > 500 ? "..." : ""}
                            </pre>
                          ) : (
                            <p>{String(m.content).slice(0, 300)}{String(m.content).length > 300 ? "..." : ""}</p>
                          )}
                        </div>

                        {/* Resources */}
                        {resourceCount > 0 && (
                          <div className="mb-3">
                            <p className="text-[11px] font-semibold mb-1.5 text-foreground">Resources</p>
                            <div className="flex flex-wrap gap-1.5">
                              {m.resources.map((r, i) => (
                                <a
                                  key={i}
                                  href={r.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  <Badge
                                    variant="info"
                                    className="text-[10px] hover:opacity-80 transition-opacity cursor-pointer"
                                  >
                                    {r.title || r.url}
                                  </Badge>
                                </a>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex items-center gap-2 border-t pt-3">
                          <Button
                            size="sm"
                            onClick={() => router.push(`/prep/materials/${m.id}`)}
                            className="rounded-lg px-3 py-1.5 text-[11px] font-semibold h-auto"
                          >
                            View
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/ai?source=prep&message=${encodeURIComponent(`Let's discuss my prep material: "${m.title}"`)}`)}
                            className="rounded-lg px-3 py-1.5 text-[11px] font-semibold text-primary h-auto"
                          >
                            Discuss with AI
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteMaterial(m.id)}
                            className="rounded-lg px-3 py-1.5 text-[11px] font-semibold text-muted-foreground ml-auto h-auto"
                          >
                            Delete
                          </Button>
                        </div>
                      </div>
                    )}
                  </Card>
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}
