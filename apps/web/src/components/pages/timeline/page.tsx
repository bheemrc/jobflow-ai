"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { useTimelineEvents, REALMS, resolveAgent } from "@/lib/use-timeline-events";
import type { SortMode, TimelinePost } from "@/lib/use-timeline-events";
import { PostCard } from "@/components/timeline/post-card";
import type { RelatedSignal } from "@/components/timeline/post-card";
import { ThinkingIndicator } from "@/components/timeline/thinking-indicator";
import { ComposePost } from "@/components/timeline/compose-post";
import { NexusSidebar } from "@/components/timeline/nexus-sidebar";
import { NotificationToast, NotificationBell, useNotifications } from "@/components/timeline/notifications";
import { useKeyboardShortcuts } from "@/lib/use-keyboard-shortcuts";
import { ShortcutHelp } from "@/components/timeline/shortcut-help";
import { buildAgentMemories } from "@/lib/agent-memory";
import { useBookmarks } from "@/lib/use-bookmarks";
import { ErrorBoundary, OfflineBar } from "@/components/error-boundary";

const EMPTY_AGENTS: string[] = [];
const FEED_PAGE_SIZE = 30;
const FEED_EST_ITEM_HEIGHT = 260;
const FEED_OVERSCAN = 6;

export default function TimelinePage() {
  const [activeRealm, setActiveRealm] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("hot");
  const { posts, agents, connected, thinkingAgents, swarms, builders, rateLimited, refreshPosts, loadMorePosts, hasMore, setPosts, handleVote } = useTimelineEvents({
    sortMode,
    pageSize: FEED_PAGE_SIZE,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const { notifications, history, unreadCount, addNotification, dismissNotification, markAllRead } = useNotifications();
  const { toggleBookmark, isBookmarked } = useBookmarks();
  const prevPostCountRef = useRef(0);
  const [focusedPostIdx, setFocusedPostIdx] = useState(-1);
  const [showShortcutHelp, setShowShortcutHelp] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const composeRef = useRef<HTMLDivElement>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const [scrollY, setScrollY] = useState(0);
  const [viewportH, setViewportH] = useState(0);
  const [feedTop, setFeedTop] = useState(0);

  // Keyboard navigation
  useKeyboardShortcuts({
    onNavigateDown: () => setFocusedPostIdx((prev) => Math.min(prev + 1, sortedPosts.length - 1)),
    onNavigateUp: () => setFocusedPostIdx((prev) => Math.max(prev - 1, 0)),
    onVoteUp: () => {
      if (focusedPostIdx >= 0 && focusedPostIdx < sortedPosts.length) {
        handleVote(sortedPosts[focusedPostIdx].id, 1);
      }
    },
    onVoteDown: () => {
      if (focusedPostIdx >= 0 && focusedPostIdx < sortedPosts.length) {
        handleVote(sortedPosts[focusedPostIdx].id, -1);
      }
    },
    onSearch: () => searchInputRef.current?.focus(),
    onCompose: () => {
      composeRef.current?.querySelector("textarea")?.focus();
    },
    onEscape: () => {
      if (showShortcutHelp) setShowShortcutHelp(false);
      else setFocusedPostIdx(-1);
    },
    onHelp: () => setShowShortcutHelp((prev) => !prev),
  });

  // Trigger notifications when new agent posts arrive
  useEffect(() => {
    if (posts.length > prevPostCountRef.current && prevPostCountRef.current > 0) {
      // Find new posts (they appear at the front)
      const newCount = posts.length - prevPostCountRef.current;
      const newPosts = posts.slice(0, newCount);
      for (const p of newPosts) {
        if (p.agent !== "user") {
          const agent = resolveAgent(p.agent, agents, p.context);
          const preview = p.content.slice(0, 80) + (p.content.length > 80 ? "..." : "");
          addNotification(p.agent, preview, p.context?.consensus_synthesis ? "swarm" : "post");
        }
      }
    }
    prevPostCountRef.current = posts.length;
  }, [posts, agents, addNotification]);

  // Clear expired local priority boosts so sort order settles naturally
  useEffect(() => {
    const now = Date.now();
    let nextExpiry = Infinity;
    for (const p of posts) {
      if (p.local_priority && p.local_priority > now) {
        nextExpiry = Math.min(nextExpiry, p.local_priority);
      }
    }
    if (nextExpiry === Infinity) return;
    const delay = Math.max(0, nextExpiry - now + 50);
    const timer = setTimeout(() => {
      setPosts((prev) =>
        prev.map((p) =>
          p.local_priority && p.local_priority <= Date.now()
            ? { ...p, local_priority: undefined }
            : p
        )
      );
    }, delay);
    return () => clearTimeout(timer);
  }, [posts, setPosts]);

  // Infer realm from post context/content
  const getPostRealm = useCallback((post: { realm?: string; content: string; post_type: string; context: Record<string, unknown> }): string => {
    if (post.realm) return post.realm;
    const c = post.content.toLowerCase();
    const ctx = post.context;
    if (ctx.event === "bot_completed" || post.post_type === "discovery") return "hunt";
    if (c.includes("leetcode") || c.includes("algorithm") || c.includes("data structure") || c.includes("coding problem")) return "cipher";
    if (c.includes("system design") || c.includes("architecture") || c.includes("scalab") || c.includes("distributed")) return "blueprint";
    if (c.includes("interview") || c.includes("star answer") || c.includes("behavioral") || c.includes("prep for")) return "arena";
    if (c.includes("resume") || c.includes("portfolio") || c.includes("cover letter") || c.includes("tailor")) return "forge";
    if (c.includes("company") || c.includes("glassdoor") || c.includes("salary") || c.includes("market") || c.includes("compensation")) return "intel";
    if (c.includes("offer") || c.includes("congrat") || c.includes("accepted") || c.includes("milestone") || c.includes("celebration")) return "summit";
    if (c.includes("job") || c.includes("role") || c.includes("opportunity") || c.includes("position") || c.includes("pipeline")) return "hunt";
    return "commons";
  }, []);

  // Precompute realms on posts (avoids inline spread in PostCard render)
  const postsWithRealms = useMemo(() =>
    posts.map((p) => p.realm ? p : { ...p, realm: getPostRealm(p) }),
    [posts, getPostRealm]
  );

  // Filter
  const realmFiltered = useMemo(() =>
    activeRealm === "all" ? postsWithRealms : postsWithRealms.filter((p) => p.realm === activeRealm),
    [postsWithRealms, activeRealm]
  );
  const searchFiltered = useMemo(() => {
    if (!searchQuery) return realmFiltered;
    const q = searchQuery.toLowerCase();
    return realmFiltered.filter((p) => {
      if (p.content.toLowerCase().includes(q)) return true;
      const agent = resolveAgent(p.agent, agents, p.context);
      return agent.displayName.toLowerCase().includes(q);
    });
  }, [realmFiltered, searchQuery, agents]);

  const sortedPosts = searchFiltered;
  const feedClassName = sortedPosts.length <= 24 ? "stagger" : "";

  useEffect(() => {
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
  }, []);

  useEffect(() => {
    if (!feedRef.current) return;
    const rect = feedRef.current.getBoundingClientRect();
    setFeedTop(rect.top + window.scrollY);
  }, [sortedPosts.length]);

  const totalPosts = sortedPosts.length;
  const windowStart = Math.max(0, Math.floor((scrollY - feedTop) / FEED_EST_ITEM_HEIGHT) - FEED_OVERSCAN);
  const windowCount = Math.ceil(viewportH / FEED_EST_ITEM_HEIGHT) + FEED_OVERSCAN * 2;
  const windowEnd = Math.min(totalPosts, windowStart + windowCount);
  const windowedPosts = sortedPosts.slice(windowStart, windowEnd);
  const topSpacer = windowStart * FEED_EST_ITEM_HEIGHT;
  const bottomSpacer = Math.max(0, (totalPosts - windowEnd) * FEED_EST_ITEM_HEIGHT);

  useEffect(() => {
    if (focusedPostIdx < 0) return;
    if (focusedPostIdx < windowStart || focusedPostIdx >= windowEnd) {
      const target = feedTop + focusedPostIdx * FEED_EST_ITEM_HEIGHT - 120;
      window.scrollTo({ top: Math.max(0, target), behavior: "smooth" });
    }
  }, [focusedPostIdx, windowStart, windowEnd, feedTop]);

  // Agent memory profiles (only recompute when post count changes, not on votes/reactions)
  const postCount = posts.length;
  const agentMemories = useMemo(() => buildAgentMemories(posts), [postCount]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cross-reference: find related signals per post (optimized with inverted index)
  // Use post IDs as dependency key to avoid recomputing on vote/reaction changes
  // Numeric sentinel: changes when top-level post IDs change (add/remove), avoids string allocation
  const postIdKey = useMemo(() => {
    let hash = 0;
    for (const p of posts) {
      if (!p.parent_id) hash = (hash * 31 + p.id) | 0;
    }
    return hash;
  }, [posts]);
  const relatedSignalsMap = useMemo(() => {
    const map = new Map<number, RelatedSignal[]>();
    const topLevelPosts = posts.filter(p => !p.parent_id);
    if (topLevelPosts.length < 2) return map;

    const stopWords = new Set(["the","a","an","is","are","was","to","of","and","in","for","on","with","at","by","from","this","that","it","be","as","or","but","not","can","will","just","have","has","had","do","we","you","they","my","your","our","so","if","no","all"]);

    // Build inverted index: keyword -> Set<post.id>
    const invertedIndex = new Map<string, Set<number>>();
    const postKeywords = new Map<number, Set<string>>();

    for (const p of topLevelPosts) {
      const words = p.content.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/)
        .filter((w) => w.length > 3 && !stopWords.has(w));
      const ctx = p.context || {};
      if (ctx.company) words.push(String(ctx.company).toLowerCase());
      if (ctx.role) words.push(String(ctx.role).toLowerCase());
      if (ctx.topic) words.push(String(ctx.topic).toLowerCase());
      const kwSet = new Set(words);
      postKeywords.set(p.id, kwSet);
      for (const kw of kwSet) {
        let ids = invertedIndex.get(kw);
        if (!ids) { ids = new Set(); invertedIndex.set(kw, ids); }
        ids.add(p.id);
      }
    }

    // Use inverted index to find related posts (avoids O(n^2) comparisons)
    const postById = new Map(topLevelPosts.map(p => [p.id, p]));
    for (const p of topLevelPosts) {
      const myKws = postKeywords.get(p.id);
      if (!myKws || myKws.size === 0) continue;

      const scores = new Map<number, string[]>();
      for (const kw of myKws) {
        const ids = invertedIndex.get(kw);
        if (!ids) continue;
        for (const otherId of ids) {
          if (otherId === p.id) continue;
          let shared = scores.get(otherId);
          if (!shared) { shared = []; scores.set(otherId, shared); }
          if (shared.length < 4) shared.push(kw); // cap to save memory
        }
      }

      const candidates: { id: number; agent: string; preview: string; shared: string[] }[] = [];
      for (const [otherId, shared] of scores) {
        if (shared.length < 2) continue;
        const other = postById.get(otherId)!;
        candidates.push({
          id: other.id,
          agent: other.agent,
          preview: other.content.slice(0, 60) + (other.content.length > 60 ? "..." : ""),
          shared,
        });
      }
      if (candidates.length > 0) {
        candidates.sort((a, b) => b.shared.length - a.shared.length);
        map.set(p.id, candidates.slice(0, 2).map((c) => ({
          id: c.id,
          agent: c.agent,
          preview: c.preview,
          sharedTopics: c.shared.slice(0, 3),
        })));
      }
    }
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postIdKey]);

  // Realm counts (memoized)
  const realmsWithCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of postsWithRealms) {
      const r = p.realm || "commons";
      counts.set(r, (counts.get(r) || 0) + 1);
    }
    return REALMS.map((r) => ({
      ...r,
      signal_count: r.id === "all" ? postsWithRealms.length : (counts.get(r.id) || 0),
    }));
  }, [postsWithRealms]);

  // Collect unique agents from posts (memoized)
  const activeAgentKeys = useMemo(() =>
    [...new Set(posts.map((p) => p.agent).filter((a) => a !== "user"))],
    [posts]
  );
  const activeAgentsResolved = useMemo(() =>
    activeAgentKeys.map((key) => ({
      key,
      ...resolveAgent(key, agents),
    })),
    [activeAgentKeys, agents]
  );

  useEffect(() => { refreshPosts(); }, [refreshPosts]);

  const handlePost = useCallback(async (content: string) => {
    // Optimistic update: show user post immediately
    const optimisticId = -Date.now(); // negative temp ID
    const optimisticPost: TimelinePost = {
      id: optimisticId,
      agent: "user",
      post_type: "thought",
      content,
      parent_id: null,
      context: {},
      reactions: {},
      visibility: "public",
      pinned: false,
      created_at: new Date().toISOString(),
      votes: 0,
      user_vote: 0,
      reply_count: 0,
      local_priority: Date.now() + 2 * 60_000,
    };
    setPosts((prev) => [optimisticPost, ...prev]);

    // Scroll feed to top so user sees their new post
    const feed = document.getElementById("nexus-feed");
    if (feed) feed.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      const res = await fetch("/api/ai/timeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        // Show error from backend
        const errorMsg = data?.detail?.[0]?.msg || data?.detail || "Failed to post";
        addNotification("system", `\u26A0\uFE0F ${errorMsg}`, "error");
        setPosts((prev) => prev.filter((p) => p.id !== optimisticId));
        return;
      }

      // Replace optimistic post with real one if backend returned it
      if (data?.post?.id) {
        setPosts((prev) =>
          prev.map((p) => (p.id === optimisticId ? { ...optimisticPost, ...data.post } : p))
        );
      }
    } catch (err) {
      // Remove optimistic post on failure and show error
      setPosts((prev) => prev.filter((p) => p.id !== optimisticId));
      addNotification("system", `\u26A0\uFE0F Network error: ${err instanceof Error ? err.message : "Failed to post"}`, "error");
    }
  }, [setPosts, addNotification]);

  const handleReply = useCallback(async (postId: number, content: string) => {
    try {
      const res = await fetch(`/api/ai/timeline/${postId}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const errorMsg = data?.detail?.[0]?.msg || data?.detail || "Failed to reply";
        addNotification("system", `\u26A0\uFE0F ${errorMsg}`, "error");
      }
    } catch (err) {
      addNotification("system", `\u26A0\uFE0F Network error: ${err instanceof Error ? err.message : "Failed to reply"}`, "error");
    }
  }, [addNotification]);

  const handleReact = useCallback(async (postId: number, emoji: string) => {
    try {
      await fetch(`/api/ai/timeline/${postId}/react`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: "user", emoji }),
      });
    } catch {}
  }, []);

  const handlePin = useCallback(async (postId: number, pinned: boolean) => {
    try {
      await fetch(`/api/ai/timeline/${postId}/pin`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned }),
      });
      refreshPosts();
    } catch {}
  }, [refreshPosts]);

  const handleDelete = useCallback(async (postId: number) => {
    try {
      await fetch(`/api/ai/timeline/${postId}`, { method: "DELETE" });
      refreshPosts();
    } catch {}
  }, [refreshPosts]);

  const activeRealmData = REALMS.find((r) => r.id === activeRealm);
  const sortOptions: { value: SortMode; label: string; icon: string }[] = [
    { value: "hot", label: "Resonating", icon: "\u25C8" },
    { value: "new", label: "Latest", icon: "\u25C6" },
    { value: "top", label: "Amplified", icon: "\u25B3" },
    { value: "active", label: "Converging", icon: "\u2B21" },
  ];

  return (
    <div className="min-h-screen bg-background" role="main" aria-label="Nexus Timeline">
      {/* Skip to content link */}
      <a
        href="#nexus-feed"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[200] focus:px-4 focus:py-2 focus:rounded-lg focus:text-[12px] focus:font-bold focus:bg-primary focus:text-white"
      >
        Skip to feed
      </a>
      {/* Screen reader live region for connection status */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {connected ? `Connected. ${posts.length} signals loaded.` : "Disconnected from Nexus."}
      </div>
      <OfflineBar visible={!connected && posts.length > 0} />
      {rateLimited && (
        <div className="fixed top-3 left-1/2 -translate-x-1/2 z-[100] px-4 py-2 rounded-xl text-[11px] font-medium animate-fade-in bg-warning/10 border border-warning/25 text-warning">
          Agents slowing down -- daily activity cap reached
        </div>
      )}
      <NotificationToast notifications={notifications} agents={agents} onDismiss={dismissNotification} />
      <ShortcutHelp open={showShortcutHelp} onClose={() => setShowShortcutHelp(false)} />
      <div className="max-w-[1200px] mx-auto px-3 sm:px-4 pt-4 sm:pt-6 pb-16 animate-page-enter">
        {/* === Header === */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-[18px] sm:text-[20px]">&#x2B21;</span>
                <h1 className="text-[18px] sm:text-[22px] font-bold tracking-tight text-foreground">
                  The Nexus
                </h1>
              </div>
              {/* Pulse indicator */}
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-full border",
                  connected
                    ? "bg-green-500/[0.08] border-green-500/15"
                    : "bg-destructive/[0.08] border-destructive/15"
                )}
              >
                <div
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    connected
                      ? "bg-green-400 shadow-[0_0_8px_rgba(86,211,100,0.6)] animate-pulse"
                      : "bg-destructive"
                  )}
                />
                <span
                  className={cn(
                    "text-[10px] font-bold tracking-wider uppercase data-mono",
                    connected ? "text-green-400" : "text-destructive"
                  )}
                >
                  {connected ? `${activeAgentKeys.length} minds active` : "Disconnected"}
                </span>
              </div>
            </div>

            {/* Search + Bell */}
            <div className="flex items-center gap-2">
              <div className="relative hidden sm:block">
                <Input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search signals... (press /)"
                  aria-label="Search signals"
                  className="w-[200px] md:w-[260px] rounded-xl pl-9 text-[12px] h-9"
                />
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground"
                  fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
              </div>
              <NotificationBell
                history={history}
                unreadCount={unreadCount}
                agents={agents}
                onMarkRead={markAllRead}
              />
            </div>
          </div>

          {/* === Realm Navigation === */}
          <nav className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none mb-4" aria-label="Realm navigation">
            {realmsWithCounts.map((realm) => {
              const isActive = activeRealm === realm.id;
              return (
                <button
                  key={realm.id}
                  onClick={() => setActiveRealm(realm.id)}
                  aria-pressed={isActive}
                  aria-label={`${realm.name} realm${realm.signal_count > 0 ? ` (${realm.signal_count} signals)` : ""}`}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold whitespace-nowrap transition-all duration-200 shrink-0 focus-visible:ring-2 focus-visible:ring-offset-1 border",
                    isActive
                      ? "shadow-sm"
                      : "bg-muted text-muted-foreground border-border hover:bg-accent"
                  )}
                  style={isActive ? {
                    background: `${realm.color}18`,
                    color: realm.color,
                    borderColor: `${realm.color}35`,
                    boxShadow: `0 0 16px ${realm.glow}`,
                  } : undefined}
                >
                  <span className="text-[11px]">{realm.icon}</span>
                  {realm.name}
                  {realm.signal_count > 0 && (
                    <span className="data-mono text-[9px] opacity-60">{realm.signal_count}</span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* === Sort Bar === */}
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-0.5 p-0.5 rounded-lg bg-muted" role="tablist" aria-label="Sort mode">
              {sortOptions.map((opt) => {
                const isActive = sortMode === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setSortMode(opt.value)}
                    role="tab"
                    aria-selected={isActive}
                    aria-label={`Sort by ${opt.label}`}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium transition-all duration-150 focus-visible:ring-2 focus-visible:ring-offset-1",
                      isActive
                        ? "bg-accent text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <span className="text-[9px] opacity-70">{opt.icon}</span>
                    {opt.label}
                  </button>
                );
              })}
            </div>

            {activeRealmData && activeRealm !== "all" && (
              <span className="text-[11px] text-muted-foreground">
                {activeRealmData.description}
              </span>
            )}
          </div>
        </div>

        {/* === Two-column layout === */}
        <div className="flex gap-6">
          {/* Main Feed */}
          <div className="flex-1 min-w-0">
            {/* Compose */}
            <div className="mb-4" ref={composeRef}>
              <ErrorBoundary label="Compose">
                <ComposePost agents={agents} onPost={handlePost} />
              </ErrorBoundary>
            </div>

            {/* Global convergence indicator */}
            {(thinkingAgents.get("global")?.agents.length ?? 0) > 0 && (
              <div className="mb-4 animate-fade-in">
                <ThinkingIndicator
                  agents={thinkingAgents.get("global")!.agents}
                  personalities={agents}
                />
              </div>
            )}

            {/* Signal Feed */}
            <div className="space-y-3">
              {!connected && posts.length === 0 ? (
                // Skeleton loading state
                <div className="space-y-3 stagger">
                  {[1, 2, 3, 4].map((i) => (
                    <Card key={i} className="rounded-2xl p-4">
                      <div className="flex items-center gap-3 mb-3">
                        <Skeleton className="h-9 w-9 rounded-xl" />
                        <div className="flex-1">
                          <Skeleton className="h-3 w-[30%] mb-1.5" />
                          <Skeleton className="h-2 w-[20%]" />
                        </div>
                        <Skeleton className="h-3 w-8" />
                      </div>
                      <div className="space-y-2">
                        <Skeleton className="h-3 w-[92%]" />
                        <Skeleton className="h-3 w-[68%]" />
                        <Skeleton className="h-3 w-[80%]" />
                      </div>
                      <Separator className="mt-3" />
                      <div className="flex items-center gap-3 pt-3">
                        <Skeleton className="h-3 w-12" />
                        <Skeleton className="h-3 w-14" />
                      </div>
                    </Card>
                  ))}
                </div>
              ) : sortedPosts.length === 0 ? (
                <Card className="rounded-2xl p-12 text-center relative overflow-hidden">
                  <div
                    className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[250px] rounded-full blur-[100px] pointer-events-none"
                    style={{ background: activeRealmData?.glow || "rgba(88, 166, 255, 0.06)" }}
                  />
                  <div className="relative">
                    <div className="text-[36px] mb-4 opacity-30">&#x2B21;</div>
                    <h3 className="text-[16px] font-semibold mb-2 text-foreground">
                      {activeRealm !== "all"
                        ? `${activeRealmData?.name || activeRealm} is quiet`
                        : searchQuery
                        ? "No matching signals"
                        : "The Nexus awaits"}
                    </h3>
                    <p className="text-[13px] max-w-[360px] mx-auto leading-relaxed text-muted-foreground">
                      {activeRealm !== "all" || searchQuery
                        ? "Try a different realm or search."
                        : "Post a question, save a job, or run a bot. Agents will emerge to assist."}
                    </p>
                  </div>
                </Card>
              ) : (
                <div id="nexus-feed" ref={feedRef} className={feedClassName} role="feed" aria-label="Signal feed" aria-busy={!connected}>
                  {topSpacer > 0 && <div style={{ height: topSpacer }} />}
                  {windowedPosts.map((post, idx) => {
                    const actualIdx = windowStart + idx;
                    return (
                      <PostCard
                        key={post.id}
                        post={post}
                        agents={agents}
                        agentMemory={agentMemories.get(post.agent)}
                        relatedSignals={relatedSignalsMap.get(post.id)}
                        thinkingAgents={thinkingAgents.get(post.id)?.agents ?? EMPTY_AGENTS}
                        swarm={swarms.get(post.id)}
                        builders={builders.get(post.id)}
                        onReply={handleReply}
                        onReact={handleReact}
                        onPin={handlePin}
                        onDelete={handleDelete}
                        onVote={handleVote}
                        onBookmark={toggleBookmark}
                        isBookmarked={isBookmarked(post.id)}
                        isFocused={actualIdx === focusedPostIdx}
                      />
                    );
                  })}
                  {bottomSpacer > 0 && <div style={{ height: bottomSpacer }} />}
                </div>
              )}
            </div>

            {hasMore && (
              <div className="mt-6 text-center">
                <Button
                  variant="ghost"
                  onClick={loadMorePosts}
                  className="px-5 text-[12px]"
                >
                  Load earlier signals
                </Button>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="w-[300px] shrink-0 hidden lg:block">
            <div className="sticky top-6">
              <ErrorBoundary label="Sidebar">
                <NexusSidebar
                  agents={activeAgentsResolved}
                  realms={realmsWithCounts}
                  activeRealm={activeRealm}
                  onRealmChange={setActiveRealm}
                  signalCount={posts.length}
                  connected={connected}
                  posts={posts}
                />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
