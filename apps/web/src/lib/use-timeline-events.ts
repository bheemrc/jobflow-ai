"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export interface TimelinePost {
  id: number;
  agent: string;
  post_type: string;
  content: string;
  parent_id: number | null;
  context: Record<string, unknown>;
  reactions: Record<string, string>;
  visibility: string;
  pinned: boolean;
  created_at: string;
  reply_count?: number;
  // Signal features
  votes?: number;
  user_vote?: 1 | -1 | 0;
  realm?: string;
  flair?: string;
  awards?: string[];
  // Client-only priority to keep newly posted items visible near the top
  local_priority?: number;
}

export interface AgentPersonality {
  display_name: string;
  avatar: string;
  voice: string;
  bio: string;
  // Extended agent profile
  reputation?: number;
  role?: string;
  expertise?: string[];
  posts_count?: number;
  joined_at?: string;
}

export type SortMode = "hot" | "new" | "top" | "active";

// ═══════════════════════════════════════════════════════════════════
// NEXUS DESIGN LANGUAGE
// Posts = "Signals", Channels = "Realms", Upvote = "Amplify"
// Swarm = "Convergence", Threads = "Chains"
// ═══════════════════════════════════════════════════════════════════

export interface Realm {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  glow: string;
  signal_count: number;
}

export const REALMS: Realm[] = [
  { id: "all", name: "All Signals", description: "The full intelligence stream", icon: "⬡", color: "#58A6FF", glow: "rgba(88, 166, 255, 0.15)", signal_count: 0 },
  { id: "hunt", name: "The Hunt", description: "Opportunity discovery & pipeline intelligence", icon: "⚡", color: "#F97316", glow: "rgba(249, 115, 22, 0.15)", signal_count: 0 },
  { id: "forge", name: "The Forge", description: "Resume crafting, portfolio, & personal brand", icon: "🔥", color: "#EF4444", glow: "rgba(239, 68, 68, 0.15)", signal_count: 0 },
  { id: "arena", name: "The Arena", description: "Interview strategy, STAR stories, & mock prep", icon: "♟️", color: "#A78BFA", glow: "rgba(167, 139, 250, 0.15)", signal_count: 0 },
  { id: "cipher", name: "The Cipher", description: "Algorithms, data structures, & coding mastery", icon: "◈", color: "#22D3EE", glow: "rgba(34, 211, 238, 0.15)", signal_count: 0 },
  { id: "blueprint", name: "Blueprint", description: "System architecture & design patterns", icon: "△", color: "#818CF8", glow: "rgba(129, 140, 248, 0.15)", signal_count: 0 },
  { id: "intel", name: "Intel", description: "Company research, salary data, & market signals", icon: "◉", color: "#4ADE80", glow: "rgba(74, 222, 128, 0.15)", signal_count: 0 },
  { id: "summit", name: "The Summit", description: "Wins, offers, milestones, & breakthroughs", icon: "✦", color: "#FBBF24", glow: "rgba(251, 191, 36, 0.15)", signal_count: 0 },
  { id: "commons", name: "Commons", description: "Open discussion, motivation, & support", icon: "⊕", color: "#94A3B8", glow: "rgba(148, 163, 184, 0.12)", signal_count: 0 },
];

// ═══════════════════════════════════════════════════════════════════
// DYNAMIC AGENT IDENTITY SYSTEM
// Agents are NOT fixed — they emerge from missions.
// The backend invents agents on-the-fly with names, roles, expertise.
// This helper resolves any agent (known or dynamic) to display info.
// ═══════════════════════════════════════════════════════════════════

// Color palette for dynamically spawned agents (deterministic by name hash)
const AGENT_COLORS = [
  "#F97316", "#EF4444", "#A78BFA", "#22D3EE", "#818CF8",
  "#4ADE80", "#FBBF24", "#F472B6", "#58A6FF", "#56D364",
  "#E879F9", "#FB923C", "#34D399", "#38BDF8", "#C084FC",
];

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function resolveAgent(
  agentKey: string,
  agents: Record<string, AgentPersonality>,
  postContext?: Record<string, unknown>
): { displayName: string; avatar: string; role: string; color: string; bio: string; isDynamic: boolean } {
  // 1. Check if the agent has a personality from the backend (covers both static + dynamic)
  const personality = agents[agentKey];
  if (personality) {
    const colorIdx = hashString(agentKey) % AGENT_COLORS.length;
    return {
      displayName: personality.display_name,
      avatar: personality.avatar,
      role: personality.role || personality.bio?.split(".")[0] || "",
      color: AGENT_COLORS[colorIdx],
      bio: personality.bio,
      isDynamic: !!(personality as AgentPersonality & { expertise?: string[] }).expertise,
    };
  }

  // 2. Check dynamic_agent context on the post itself (swarm-spawned agents)
  const dynCtx = (postContext?.dynamic_agent ?? null) as {
    display_name?: string;
    avatar?: string;
    expertise?: string;
    tone?: string;
  } | null;

  if (dynCtx) {
    const colorIdx = hashString(agentKey) % AGENT_COLORS.length;
    return {
      displayName: dynCtx.display_name || formatAgentName(agentKey),
      avatar: dynCtx.avatar || "◇",
      role: dynCtx.expertise || "",
      color: AGENT_COLORS[colorIdx],
      bio: dynCtx.expertise || "",
      isDynamic: true,
    };
  }

  // 3. User
  if (agentKey === "user") {
    return {
      displayName: "You",
      avatar: "👤",
      role: "Human",
      color: "#58A6FF",
      bio: "",
      isDynamic: false,
    };
  }

  // 4. Unknown agent — format name nicely, assign deterministic color
  const colorIdx = hashString(agentKey) % AGENT_COLORS.length;
  return {
    displayName: formatAgentName(agentKey),
    avatar: "◇",
    role: "Dynamic Agent",
    color: AGENT_COLORS[colorIdx],
    bio: "",
    isDynamic: true,
  };
}

function formatAgentName(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000];

// Key is thread_id (number) or "global" for top-level thoughts
export type ThinkingMap = Map<string | number, { agents: string[]; startedAt: number }>;

export interface SwarmInfo {
  started: boolean;
  activations: number;
  maxActivations: number;
  agents: string[];
  complete: boolean;
  phase?: "research" | "debate" | "synthesis";
}

// Key is post_id
export type SwarmMap = Map<number, SwarmInfo>;

export interface BuilderInfo {
  builderId: string;
  postId: number;
  title: string;
  agentName: string;
  percent: number;
  stage: string;
  materialId: number | null;
  complete: boolean;
}

// Key is post_id
export type BuilderMap = Map<number, BuilderInfo[]>;

// Compute "hot" score for sorting (Reddit-style)
// Takes pre-computed timestamp to avoid repeated Date parsing in comparisons
function hotScore(post: TimelinePost, createdMs: number, nowMs: number): number {
  const votes = post.votes || 0;
  const age = (nowMs - createdMs) / 3600000; // hours
  const replies = post.reply_count || 0;
  const engagement = votes + replies * 2;
  const recencyBoost = Math.max(0, 5 * Math.exp(-age / 2));
  return (engagement + recencyBoost) / Math.pow(age + 2, 1.5);
}

export function sortPosts(posts: TimelinePost[], mode: SortMode): TimelinePost[] {
  const now = Date.now();

  // Pre-compute timestamps once to avoid repeated Date parsing in sort comparisons
  const timestamps = new Map<number, number>();
  for (const p of posts) {
    timestamps.set(p.id, new Date(p.created_at).getTime());
  }
  const getTs = (p: TimelinePost) => timestamps.get(p.id) || 0;

  const sorted = [...posts];
  const localPriority = (post: TimelinePost) =>
    post.local_priority && post.local_priority > now ? post.local_priority : 0;
  switch (mode) {
    case "hot":
      return sorted.sort((a, b) => {
        if (a.pinned && !b.pinned) return -1;
        if (!a.pinned && b.pinned) return 1;
        const aLocal = localPriority(a);
        const bLocal = localPriority(b);
        if (aLocal !== bLocal) return bLocal - aLocal;
        return hotScore(b, getTs(b), now) - hotScore(a, getTs(a), now);
      });
    case "new":
      return sorted.sort((a, b) => {
        if (a.pinned && !b.pinned) return -1;
        if (!a.pinned && b.pinned) return 1;
        const aLocal = localPriority(a);
        const bLocal = localPriority(b);
        if (aLocal !== bLocal) return bLocal - aLocal;
        return getTs(b) - getTs(a);
      });
    case "top":
      return sorted.sort((a, b) => {
        if (a.pinned && !b.pinned) return -1;
        if (!a.pinned && b.pinned) return 1;
        const aLocal = localPriority(a);
        const bLocal = localPriority(b);
        if (aLocal !== bLocal) return bLocal - aLocal;
        return (b.votes || 0) - (a.votes || 0);
      });
    case "active":
      return sorted.sort((a, b) => {
        if (a.pinned && !b.pinned) return -1;
        if (!a.pinned && b.pinned) return 1;
        const aLocal = localPriority(a);
        const bLocal = localPriority(b);
        if (aLocal !== bLocal) return bLocal - aLocal;
        const aScore = (a.reply_count || 0) + Object.keys(a.reactions).length;
        const bScore = (b.reply_count || 0) + Object.keys(b.reactions).length;
        return bScore - aScore;
      });
    default:
      return sorted;
  }
}

export interface RateLimitInfo {
  agent: string;
  reason: string;
  timestamp: number;
}

export function useTimelineEvents(options?: { sortMode?: SortMode; pageSize?: number }) {
  const [posts, setPosts] = useState<TimelinePost[]>([]);
  const [agents, setAgents] = useState<Record<string, AgentPersonality>>({});
  const [connected, setConnected] = useState(false);
  const [thinkingAgents, setThinkingAgents] = useState<ThinkingMap>(new Map());
  const [swarms, setSwarms] = useState<SwarmMap>(new Map());
  const [builders, setBuilders] = useState<BuilderMap>(new Map());
  const [rateLimited, setRateLimited] = useState<RateLimitInfo | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const offsetRef = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const mergeIncomingPosts = useCallback((prev: TimelinePost[], incoming: TimelinePost[]) => {
    // Smart merge: preserve object references and client-only fields for unchanged posts
    if (prev.length === 0) return incoming;
    const prevById = new Map(prev.map((p) => [p.id, p]));
    let changed = prev.length !== incoming.length;
    const merged = incoming.map((newPost) => {
      const existing = prevById.get(newPost.id);
      if (!existing) { changed = true; return newPost; }
      const localPriority = existing.local_priority;
      // Compare key fields to detect real changes
      if (
        existing.content === newPost.content &&
        existing.votes === newPost.votes &&
        existing.user_vote === newPost.user_vote &&
        existing.reply_count === newPost.reply_count &&
        existing.pinned === newPost.pinned &&
        Object.keys(existing.reactions ?? {}).join() === Object.keys(newPost.reactions ?? {}).join() &&
        Object.values(existing.reactions ?? {}).join() === Object.values(newPost.reactions ?? {}).join()
      ) {
        return existing; // preserve reference (keeps local_priority)
      }
      changed = true;
      return localPriority ? { ...newPost, local_priority: localPriority } : newPost;
    });
    return changed ? merged : prev;
  }, []);

  // Fetch agent personalities on mount
  useEffect(() => {
    fetch("/api/ai/timeline/agents")
      .then((r) => r.json())
      .then((data) => {
        if (data?.agents) setAgents(data.agents);
      })
      .catch(() => {});
  }, []);

  const handleEvent = useCallback((event: Record<string, unknown>) => {
    switch (event.type) {
      case "timeline_state":
        if (Array.isArray(event.posts)) {
          const incoming = event.posts as TimelinePost[];
          offsetRef.current = incoming.length;
          const pageSize = options?.pageSize ?? 20;
          setHasMore(incoming.length >= pageSize);
          setPosts((prev) => mergeIncomingPosts(prev, incoming));
        }
        break;

      case "agent_thinking": {
        const thinkAgent = event.agent as string;
        const threadKey = (event.thread_id as string | number) ?? "global";
        setThinkingAgents((prev) => {
          const next = new Map(prev);
          const entry = next.get(threadKey) ?? { agents: [], startedAt: Date.now() };
          if (!entry.agents.includes(thinkAgent)) {
            next.set(threadKey, {
              agents: [...entry.agents, thinkAgent],
              startedAt: Date.now(),
            });
          }
          return next;
        });
        break;
      }

      case "timeline_post":
        if (event.post) {
          const newPost = event.post as TimelinePost;
          const isUserPost = newPost.agent === "user";
          const boostedPost = isUserPost
            ? { ...newPost, local_priority: Date.now() + 2 * 60_000 }
            : newPost;

          // Remove agent from thinking state when their post arrives
          const postThreadKey = boostedPost.parent_id ?? "global";
          setThinkingAgents((prev) => {
            const entry = prev.get(postThreadKey);
            if (!entry) return prev;
            const filtered = entry.agents.filter((a) => a !== boostedPost.agent);
            const next = new Map(prev);
            if (filtered.length === 0) {
              next.delete(postThreadKey);
            } else {
              next.set(postThreadKey, { ...entry, agents: filtered });
            }
            return next;
          });

          setPosts((prev) => {
            // If it's a reply (has parent_id), update parent's reply_count
            if (boostedPost.parent_id) {
              return prev.map((p) =>
                p.id === boostedPost.parent_id
                  ? { ...p, reply_count: (p.reply_count || 0) + 1 }
                  : p
              );
            }
            // Dedup: skip if already present by ID
            if (prev.some((p) => p.id === boostedPost.id)) return prev;
            // Replace optimistic post (negative temp ID) with real one from backend
            const optimistic = prev.find(
              (p) => p.id < 0 && p.agent === boostedPost.agent && p.content === boostedPost.content
            );
            if (optimistic) {
              return prev.map((p) => (p.id === optimistic.id ? boostedPost : p));
            }
            // Add new top-level post to the top
            return [boostedPost, ...prev];
          });
        }
        break;

      case "timeline_reaction":
        if (event.post_id && event.agent && event.emoji) {
          setPosts((prev) =>
            prev.map((p) =>
              p.id === event.post_id
                ? {
                    ...p,
                    reactions: {
                      ...p.reactions,
                      [event.agent as string]: event.emoji as string,
                    },
                  }
                : p
            )
          );
        }
        break;

      case "timeline_vote":
        if (event.post_id && event.voter !== "user") {
          // Only update if the vote came from another voter (avoid double-counting our own)
          setPosts((prev) =>
            prev.map((p) =>
              p.id === event.post_id
                ? { ...p, votes: (event.votes as number) ?? p.votes }
                : p
            )
          );
        }
        break;

      case "swarm_started": {
        const postId = event.post_id as number;
        setSwarms((prev) => {
          const next = new Map(prev);
          next.set(postId, {
            started: true,
            activations: 0,
            maxActivations: (event.max_activations as number) || 20,
            agents: (event.initial_agents as string[]) || [],
            complete: false,
          });
          return next;
        });
        // Merge dynamic agent personalities into agents map
        const dynAgents = event.dynamic_agents as Record<string, { display_name: string; avatar: string; expertise: string; tone: string }> | undefined;
        if (dynAgents) {
          setAgents((prev) => {
            const next = { ...prev };
            for (const [agentId, info] of Object.entries(dynAgents)) {
              if (!next[agentId]) {
                next[agentId] = {
                  display_name: info.display_name,
                  avatar: info.avatar,
                  voice: info.tone || "",
                  bio: info.expertise || "",
                };
              }
            }
            return next;
          });
        }
        break;
      }

      case "agent_requested": {
        const postId = event.post_id as number;
        const agentId = (event.agent_id || event.agent) as string;
        setSwarms((prev) => {
          const next = new Map(prev);
          const info = next.get(postId);
          if (info && agentId) {
            next.set(postId, {
              ...info,
              activations: (event.activation_count as number) || info.activations + 1,
              agents: info.agents.includes(agentId)
                ? info.agents
                : [...info.agents, agentId],
            });
          }
          return next;
        });
        // Register dynamic agent info in agents map if provided
        if (event.agent_id && event.agent_name) {
          setAgents((prev) => ({
            ...prev,
            [event.agent_id as string]: {
              display_name: event.agent_name as string,
              avatar: (event.avatar as string) || "🔍",
              voice: "",
              bio: (event.expertise as string) || "",
            },
          }));
        }
        break;
      }

      case "swarm_phase": {
        const postId = event.post_id as number;
        const phase = event.phase as "research" | "debate" | "synthesis";
        setSwarms((prev) => {
          const next = new Map(prev);
          const info = next.get(postId);
          if (info) {
            next.set(postId, { ...info, phase });
          }
          return next;
        });
        break;
      }

      case "swarm_complete": {
        const postId = event.post_id as number;
        setSwarms((prev) => {
          const next = new Map(prev);
          const info = next.get(postId);
          if (info) {
            next.set(postId, {
              ...info,
              activations: (event.total_activations as number) || info.activations,
              agents: (event.agents_responded as string[]) || info.agents,
              complete: true,
            });
          }
          return next;
        });
        break;
      }

      case "builder_dispatched": {
        const postId = event.post_id as number;
        const info: BuilderInfo = {
          builderId: event.builder_id as string,
          postId,
          title: event.title as string,
          agentName: (event.agent_name as string) || "",
          percent: 0,
          stage: "queued",
          materialId: null,
          complete: false,
        };
        setBuilders((prev) => {
          const next = new Map(prev);
          const existing = next.get(postId) || [];
          next.set(postId, [...existing, info]);
          return next;
        });
        break;
      }

      case "builder_progress": {
        const postId = event.post_id as number;
        const builderId = event.builder_id as string;
        setBuilders((prev) => {
          const next = new Map(prev);
          const existing = next.get(postId);
          if (existing) {
            next.set(
              postId,
              existing.map((b) =>
                b.builderId === builderId
                  ? { ...b, percent: event.percent as number, stage: event.stage as string }
                  : b
              )
            );
          }
          return next;
        });
        break;
      }

      case "builder_complete": {
        const postId = event.post_id as number;
        const builderId = event.builder_id as string;
        setBuilders((prev) => {
          const next = new Map(prev);
          const existing = next.get(postId);
          if (existing) {
            next.set(
              postId,
              existing.map((b) =>
                b.builderId === builderId
                  ? { ...b, percent: 100, stage: "complete", materialId: event.material_id as number, complete: true }
                  : b
              )
            );
          }
          return next;
        });
        break;
      }

      case "rate_limit_hit": {
        setRateLimited({
          agent: event.agent as string,
          reason: event.reason as string,
          timestamp: Date.now(),
        });
        // Auto-clear after 10 seconds
        setTimeout(() => setRateLimited(null), 10_000);
        break;
      }

      case "heartbeat":
        reconnectAttemptRef.current = 0;
        break;
    }
  }, [mergeIncomingPosts, options?.pageSize]);

  useEffect(() => {
    const connect = () => {
      eventSourceRef.current?.close();
      const qs = new URLSearchParams();
      if (options?.sortMode) qs.set("sort", options.sortMode);
      if (options?.pageSize) qs.set("limit", String(options.pageSize));
      const es = new EventSource(`/api/ai/timeline/stream${qs.toString() ? `?${qs}` : ""}`);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        reconnectAttemptRef.current = 0;
      };

      es.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          handleEvent(event);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        es.close();
        setConnected(false);
        const attempt = Math.min(
          reconnectAttemptRef.current,
          RECONNECT_DELAYS.length - 1
        );
        const delay = RECONNECT_DELAYS[attempt];
        reconnectAttemptRef.current++;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [handleEvent, options?.sortMode, options?.pageSize]);

  // Clear stale thinking indicators after 30 seconds (failsafe)
  useEffect(() => {
    const interval = setInterval(() => {
      setThinkingAgents((prev) => {
        const now = Date.now();
        let changed = false;
        const next = new Map(prev);
        for (const [key, entry] of next) {
          if (now - entry.startedAt > 30_000) {
            next.delete(key);
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 10_000);
    return () => clearInterval(interval);
  }, []);

  const refreshPosts = useCallback(async (params?: { agent?: string; post_type?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.agent) searchParams.set("agent", params.agent);
    if (params?.post_type) searchParams.set("post_type", params.post_type);
    if (options?.sortMode) searchParams.set("sort", options.sortMode);
    if (options?.pageSize) searchParams.set("limit", String(options.pageSize));
    const qs = searchParams.toString();
    const url = `/api/ai/timeline${qs ? `?${qs}` : ""}`;
    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data?.posts) {
        const incoming = data.posts as TimelinePost[];
        offsetRef.current = incoming.length;
        setHasMore(Boolean(data?.has_more));
        setPosts((prev) => mergeIncomingPosts(prev, incoming));
      }
    } catch {
      // ignore
    }
  }, [mergeIncomingPosts, options?.sortMode, options?.pageSize]);

  const loadMorePosts = useCallback(async () => {
    if (!hasMore) return;
    const searchParams = new URLSearchParams();
    searchParams.set("offset", String(offsetRef.current));
    if (options?.pageSize) searchParams.set("limit", String(options.pageSize));
    if (options?.sortMode) searchParams.set("sort", options.sortMode);
    const url = `/api/ai/timeline?${searchParams.toString()}`;
    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data?.posts && Array.isArray(data.posts)) {
        const incoming = data.posts as TimelinePost[];
        if (incoming.length > 0) {
          offsetRef.current += incoming.length;
          setPosts((prev) => [...prev, ...incoming]);
        }
        setHasMore(Boolean(data?.has_more));
      }
    } catch {
      // ignore
    }
  }, [hasMore, options?.pageSize, options?.sortMode]);

  const handleVote = useCallback((postId: number, direction: 1 | -1) => {
    let apiDirection: number = direction;
    setPosts((prev) =>
      prev.map((p) => {
        if (p.id !== postId) return p;
        const currentVote = p.user_vote || 0;
        let newVote: 1 | -1 | 0;
        let voteDelta: number;
        if (currentVote === direction) {
          newVote = 0;
          voteDelta = -direction;
          apiDirection = 0;
        } else {
          newVote = direction;
          voteDelta = direction - currentVote;
          apiDirection = direction;
        }
        return { ...p, user_vote: newVote, votes: (p.votes || 0) + voteDelta };
      })
    );
    fetch(`/api/ai/timeline/${postId}/vote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction: apiDirection, voter: "user" }),
    }).catch(() => {});
  }, []);

  return { posts, agents, connected, thinkingAgents, swarms, builders, rateLimited, refreshPosts, loadMorePosts, hasMore, setPosts, handleVote };
}
