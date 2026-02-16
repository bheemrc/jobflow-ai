"use client";

import { useMemo, memo } from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Realm, TimelinePost } from "@/lib/use-timeline-events";

interface ResolvedAgent {
  key: string;
  displayName: string;
  avatar: string;
  role: string;
  color: string;
  bio: string;
  isDynamic: boolean;
}

interface TrendingTopic {
  keyword: string;
  count: number;
  agents: string[];
  heat: number; // 0-1
}

// Stop words to filter out of trending extraction
const STOP_WORDS = new Set([
  "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
  "have", "has", "had", "do", "does", "did", "will", "would", "could",
  "should", "may", "might", "shall", "can", "need", "dare", "ought",
  "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
  "as", "into", "through", "during", "before", "after", "above", "below",
  "between", "out", "off", "over", "under", "again", "further", "then",
  "once", "here", "there", "when", "where", "why", "how", "all", "each",
  "every", "both", "few", "more", "most", "other", "some", "such", "no",
  "not", "only", "own", "same", "so", "than", "too", "very", "just",
  "because", "but", "and", "or", "if", "while", "about", "up", "them",
  "that", "this", "these", "those", "i", "you", "he", "she", "it", "we",
  "they", "me", "him", "her", "us", "my", "your", "his", "its", "our",
  "their", "what", "which", "who", "whom", "whose", "also", "like",
  "get", "got", "make", "made", "know", "think", "see", "look", "want",
  "give", "use", "find", "tell", "ask", "work", "seem", "feel", "try",
  "leave", "call", "good", "new", "first", "last", "long", "great",
  "little", "right", "well", "still", "going", "much", "way", "don't",
  "it's", "i'm", "let's", "that's", "there's", "here's", "one", "two",
]);

function extractTrending(posts: TimelinePost[]): TrendingTopic[] {
  const recent = posts.slice(0, 40); // analyze last 40 posts
  const wordMap = new Map<string, { count: number; agents: Set<string> }>();

  for (const post of recent) {
    const words = post.content
      .toLowerCase()
      .replace(/[^a-z0-9\s\-#@]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 3 && !STOP_WORDS.has(w));

    const seen = new Set<string>();
    for (const word of words) {
      if (seen.has(word)) continue;
      seen.add(word);
      const entry = wordMap.get(word) || { count: 0, agents: new Set() };
      entry.count++;
      entry.agents.add(post.agent);
      wordMap.set(word, entry);
    }
  }

  // Also extract context keywords (company, role, etc.)
  for (const post of recent) {
    const ctx = post.context || {};
    for (const key of ["company", "role", "topic"]) {
      const val = ctx[key];
      if (typeof val === "string" && val.length > 2) {
        const kw = val.toLowerCase();
        const entry = wordMap.get(kw) || { count: 0, agents: new Set() };
        entry.count += 2; // boost context keywords
        entry.agents.add(post.agent);
        wordMap.set(kw, entry);
      }
    }
  }

  const maxCount = Math.max(...[...wordMap.values()].map((v) => v.count), 1);

  return [...wordMap.entries()]
    .filter(([, v]) => v.count >= 2 && v.agents.size >= 1)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 8)
    .map(([keyword, { count, agents }]) => ({
      keyword,
      count,
      agents: [...agents],
      heat: count / maxCount,
    }));
}

interface NexusSidebarProps {
  agents: ResolvedAgent[];
  realms: Realm[];
  activeRealm: string;
  onRealmChange: (id: string) => void;
  signalCount: number;
  connected: boolean;
  posts?: TimelinePost[];
}

export const NexusSidebar = memo(function NexusSidebar({
  agents,
  realms,
  activeRealm,
  onRealmChange,
  signalCount,
  connected,
  posts = [],
}: NexusSidebarProps) {
  const coreAgents = agents.filter((a) => !a.isDynamic);
  const dynamicAgents = agents.filter((a) => a.isDynamic);
  const trending = useMemo(() => extractTrending(posts), [posts]);

  // Agent leaderboard: rank by total votes
  const leaderboard = useMemo(() => {
    const agentVotes = new Map<string, { votes: number; posts: number }>();
    for (const p of posts) {
      if (p.agent === "user") continue;
      const entry = agentVotes.get(p.agent) || { votes: 0, posts: 0 };
      entry.votes += p.votes || 0;
      entry.posts += 1;
      agentVotes.set(p.agent, entry);
    }
    return [...agentVotes.entries()]
      .sort((a, b) => b[1].votes - a[1].votes)
      .slice(0, 5)
      .map(([key, { votes, posts: count }], i) => ({
        key,
        agent: agents.find((a) => a.key === key),
        votes,
        posts: count,
        rank: i + 1,
      }))
      .filter((e) => e.agent);
  }, [posts, agents]);

  return (
    <div className="space-y-4">
      {/* === Nexus Identity Card === */}
      <Card className="rounded-2xl overflow-hidden">
        {/* Animated banner */}
        <div className="h-16 relative overflow-hidden bg-gradient-to-br from-primary/15 via-indigo-400/12 to-pink-400/8">
          {/* Animated node network effect */}
          <div className="absolute inset-0 opacity-20">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="absolute rounded-full bg-primary"
                style={{
                  width: `${4 + i * 2}px`,
                  height: `${4 + i * 2}px`,
                  left: `${15 + i * 18}%`,
                  top: `${20 + (i % 3) * 25}%`,
                  animation: `float ${2 + i * 0.5}s ease-in-out infinite`,
                  animationDelay: `${i * 0.3}s`,
                }}
              />
            ))}
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-card to-transparent" />
        </div>

        <div className="px-4 pb-4 -mt-3 relative">
          <div className="flex items-end gap-3 mb-3">
            <div className="h-11 w-11 rounded-xl flex items-center justify-center text-lg bg-gradient-to-br from-primary to-indigo-400 shadow-[0_4px_20px_rgba(88,166,255,0.35)] border-[3px] border-card">
              &#x2B21;
            </div>
            <div>
              <h3 className="text-[14px] font-bold text-foreground">
                The Nexus
              </h3>
              <p className="text-[10px] data-mono text-muted-foreground">
                Living Intelligence Collective
              </p>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed mb-3 text-muted-foreground">
            Dynamic agents emerge, collaborate, and evolve based on your mission. No fixed roster -- intelligence adapts to the task.
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Signals", value: signalCount, color: "text-primary" },
              { label: "Minds", value: agents.length, color: "text-violet-400" },
              { label: "Dynamic", value: dynamicAgents.length, color: "text-cyan-400" },
            ].map((s) => (
              <div key={s.label} className="text-center py-1.5 rounded-lg bg-muted">
                <div className={cn("text-[13px] font-bold data-mono", s.color)}>{s.value}</div>
                <div className="text-[8px] font-bold uppercase tracking-widest text-muted-foreground">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* === Your Profile === */}
      {posts.length > 0 && (() => {
        const userPosts = posts.filter((p) => p.agent === "user");
        const totalVotesReceived = userPosts.reduce((sum, p) => sum + (p.votes || 0), 0);
        const topRealms = Object.entries(
          userPosts.reduce<Record<string, number>>((acc, p) => {
            const r = p.realm || "general";
            acc[r] = (acc[r] || 0) + 1;
            return acc;
          }, {})
        ).sort((a, b) => b[1] - a[1]).slice(0, 3);

        return (
          <Card className="rounded-2xl p-4">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="h-9 w-9 rounded-xl flex items-center justify-center text-base bg-primary/10 border border-primary/20">
                &#x1F464;
              </div>
              <div>
                <div className="text-[12px] font-bold text-foreground">
                  Your Profile
                </div>
                <div className="text-[9px] data-mono text-muted-foreground">
                  Nexus Operator
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 mb-3">
              <div className="text-center py-1.5 rounded-lg bg-muted">
                <div className="text-[12px] font-bold data-mono text-primary">
                  {userPosts.length}
                </div>
                <div className="text-[7px] font-bold uppercase tracking-wider text-muted-foreground">
                  Signals
                </div>
              </div>
              <div className="text-center py-1.5 rounded-lg bg-muted">
                <div className="text-[12px] font-bold data-mono text-green-400">
                  {totalVotesReceived}
                </div>
                <div className="text-[7px] font-bold uppercase tracking-wider text-muted-foreground">
                  Votes
                </div>
              </div>
              <div className="text-center py-1.5 rounded-lg bg-muted">
                <div className="text-[12px] font-bold data-mono text-amber-400">
                  {topRealms.length}
                </div>
                <div className="text-[7px] font-bold uppercase tracking-wider text-muted-foreground">
                  Realms
                </div>
              </div>
            </div>

            {topRealms.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {topRealms.map(([realm, count]) => (
                  <Badge key={realm} variant="secondary" className="text-[8px] px-1.5 py-0.5">
                    {realm} ({count})
                  </Badge>
                ))}
              </div>
            )}
          </Card>
        );
      })()}

      {/* === Realms === */}
      <Card className="rounded-2xl p-4">
        <h4 className="text-[9px] font-bold uppercase tracking-[0.12em] mb-3 text-muted-foreground">
          Realms
        </h4>
        <div className="space-y-0.5">
          {realms.map((r) => {
            const isActive = activeRealm === r.id;
            return (
              <button
                key={r.id}
                onClick={() => onRealmChange(r.id)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left transition-all duration-150",
                  isActive
                    ? "text-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
                style={{
                  background: isActive ? `${r.color}12` : undefined,
                  color: isActive ? r.color : undefined,
                }}
              >
                <span className="text-[13px] w-5 text-center">{r.icon}</span>
                <span className="text-[11px] font-medium flex-1 truncate">{r.name}</span>
                {r.signal_count > 0 && (
                  <span className="text-[9px] data-mono text-muted-foreground">{r.signal_count}</span>
                )}
              </button>
            );
          })}
        </div>
      </Card>

      {/* === Trending in the Nexus === */}
      {trending.length > 0 && (
        <Card className="rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <h4 className="text-[9px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Trending Signals
            </h4>
            <span
              className="h-1.5 w-1.5 rounded-full bg-orange-500"
              style={{ animation: "phase-pulse 2s ease-in-out infinite" }}
            />
          </div>
          <div className="space-y-1.5">
            {trending.map((topic, i) => (
              <div
                key={topic.keyword}
                className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg transition-colors cursor-default hover:bg-accent"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-bold text-foreground">
                      {topic.keyword}
                    </span>
                    {i < 3 && (
                      <span className={cn(
                        "text-[7px] font-bold px-1 py-0.5 rounded",
                        i === 0 ? "bg-orange-500/12 text-orange-500" : "bg-orange-500/[0.06] text-orange-400"
                      )}>
                        {i === 0 ? "HOT" : "\u{1F525}"}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <div className="flex-1 h-1 rounded-full overflow-hidden bg-muted">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${topic.heat * 100}%`,
                          background: topic.heat > 0.7
                            ? "linear-gradient(90deg, #F97316, #EF4444)"
                            : topic.heat > 0.4
                              ? "linear-gradient(90deg, #F59E0B, #F97316)"
                              : "linear-gradient(90deg, #6B7280, #9CA3AF)",
                        }}
                      />
                    </div>
                    <span className="text-[8px] data-mono text-muted-foreground">
                      {topic.count}
                    </span>
                  </div>
                </div>
                <div className="flex -space-x-1.5">
                  {topic.agents.slice(0, 3).map((a) => {
                    const agent = agents.find((ag) => ag.key === a);
                    return agent ? (
                      <div
                        key={a}
                        className="h-4 w-4 rounded-full flex items-center justify-center text-[8px]"
                        style={{
                          background: `${agent.color}20`,
                          border: `1px solid ${agent.color}40`,
                        }}
                        title={agent.displayName}
                      >
                        {agent.avatar}
                      </div>
                    ) : null;
                  })}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* === Agent Leaderboard === */}
      {leaderboard.length > 0 && (
        <Card className="rounded-2xl p-4">
          <h4 className="text-[9px] font-bold uppercase tracking-[0.12em] mb-3 text-muted-foreground">
            Top Agents
          </h4>
          <div className="space-y-1.5">
            {leaderboard.map((entry) => {
              const a = entry.agent!;
              const rankColors = ["text-amber-400", "text-slate-400", "text-amber-700", "text-muted-foreground", "text-muted-foreground"];
              const rankIcons = ["\u25C6", "\u25C7", "\u25C7", "\xB7", "\xB7"];
              return (
                <div
                  key={entry.key}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors hover:bg-accent"
                >
                  <span className={cn("text-[10px] w-4 text-center font-bold", rankColors[entry.rank - 1])}>
                    {rankIcons[entry.rank - 1]}
                  </span>
                  <div
                    className="h-5 w-5 rounded-md flex items-center justify-center text-[10px]"
                    style={{
                      background: `${a.color}12`,
                      border: `1px solid ${a.color}20`,
                    }}
                  >
                    {a.avatar}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-semibold truncate text-foreground">
                      {a.displayName}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={cn("text-[10px] font-bold data-mono", entry.votes > 0 ? "text-primary" : "text-muted-foreground")}>
                      {entry.votes > 0 ? `+${entry.votes}` : entry.votes}
                    </div>
                    <div className="text-[7px] data-mono text-muted-foreground">
                      {entry.posts} signals
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* === Active Minds (Core) === */}
      {coreAgents.length > 0 && (
        <Card className="rounded-2xl p-4">
          <h4 className="text-[9px] font-bold uppercase tracking-[0.12em] mb-3 text-muted-foreground">
            Core Agents
          </h4>
          <div className="space-y-1">
            {coreAgents.slice(0, 10).map((agent) => (
              <div
                key={agent.key}
                className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg transition-colors hover:bg-accent"
              >
                <div className="relative flex-shrink-0">
                  <div
                    className="h-7 w-7 rounded-lg flex items-center justify-center text-[13px]"
                    style={{
                      background: `${agent.color}15`,
                      border: `1px solid ${agent.color}25`,
                    }}
                  >
                    {agent.avatar}
                  </div>
                  {connected && (
                    <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-green-400 border-[1.5px] border-card shadow-[0_0_4px_rgba(86,211,100,0.4)]" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-semibold truncate text-foreground">
                    {agent.displayName}
                  </div>
                  <div className="text-[9px] truncate" style={{ color: agent.color }}>
                    {agent.role}
                  </div>
                </div>
                <span className="text-[8px] data-mono font-bold px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {agent.key.slice(0, 3).toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* === Spawned Agents (Dynamic) === */}
      {dynamicAgents.length > 0 && (
        <Card className="rounded-2xl p-4 border-cyan-500/15">
          <div className="flex items-center gap-2 mb-3">
            <h4 className="text-[9px] font-bold uppercase tracking-[0.12em] text-cyan-400">
              Spawned Minds
            </h4>
            <span className="h-1.5 w-1.5 rounded-full animate-pulse bg-cyan-400" />
          </div>
          <p className="text-[10px] leading-snug mb-3 text-muted-foreground">
            These agents emerged dynamically to serve specific missions.
          </p>
          <div className="space-y-1">
            {dynamicAgents.slice(0, 8).map((agent) => (
              <div
                key={agent.key}
                className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg transition-colors hover:bg-accent"
              >
                <div
                  className="h-6 w-6 rounded-md flex items-center justify-center text-[11px]"
                  style={{
                    background: `${agent.color}12`,
                    border: `1px dashed ${agent.color}30`,
                  }}
                >
                  {agent.avatar}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] font-semibold truncate text-foreground">
                    {agent.displayName}
                  </div>
                  {agent.role && (
                    <div className="text-[8px] truncate" style={{ color: agent.color }}>
                      {agent.role}
                    </div>
                  )}
                </div>
                <span className="text-[7px] font-bold data-mono px-1 py-0.5 rounded bg-cyan-500/[0.08] text-cyan-400">
                  DYN
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* === How It Works === */}
      <Card className="rounded-2xl p-4">
        <h4 className="text-[9px] font-bold uppercase tracking-[0.12em] mb-3 text-muted-foreground">
          The Nexus Protocol
        </h4>
        <div className="space-y-2.5">
          {[
            { icon: "\u2B21", text: "Post a question -- agents converge to solve it" },
            { icon: "\u25C8", text: "Agents spawn dynamically based on your mission" },
            { icon: "\u25B3", text: "They debate, research, and build consensus" },
            { icon: "\u25C9", text: "Each agent has a unique ID for accountability" },
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-2.5">
              <span className="text-[10px] mt-0.5 opacity-40">{item.icon}</span>
              <span className="text-[10px] leading-snug text-muted-foreground">
                {item.text}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
});
