"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { ChatCard, StartChatModal, type GroupChatConfig } from "@/components/group-chat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { GroupChat } from "@/lib/types";

type FilterType = "all" | "active" | "concluded";
type SortType = "recent" | "active" | "participants";

export default function GroupChatsPage() {
  const router = useRouter();
  const [chats, setChats] = useState<GroupChat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showStartModal, setShowStartModal] = useState(false);
  const [filter, setFilter] = useState<FilterType>("all");
  const [sort, setSort] = useState<SortType>("recent");
  const [searchQuery, setSearchQuery] = useState("");

  const fetchChats = async () => {
    try {
      const res = await fetch("/api/ai/group-chats");
      if (res.ok) {
        const data = await res.json();
        setChats(data.group_chats || []);
      }
    } catch (e) {
      console.error("Failed to fetch group chats:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchChats();
    // Poll for updates every 10 seconds
    const interval = setInterval(fetchChats, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleStartChat = async (topic: string, participants: string[], chatConfig: GroupChatConfig) => {
    const res = await fetch("/api/ai/group-chats/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic,
        participants,
        config: {
          max_turns: chatConfig.maxTurns,
          allowed_tools: chatConfig.allowedTools,
        },
      }),
    });

    if (res.ok) {
      const data = await res.json();
      router.push(`/group-chats/${data.group_chat_id}`);
    } else {
      throw new Error("Failed to start chat");
    }
  };

  // Filter and sort chats
  const processedChats = useMemo(() => {
    let result = [...chats];

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (chat) =>
          chat.topic.toLowerCase().includes(query) ||
          chat.participants.some((p) => p.toLowerCase().includes(query))
      );
    }

    // Apply status filter
    if (filter === "active") {
      result = result.filter((c) => c.status === "active" || c.status === "paused");
    } else if (filter === "concluded") {
      result = result.filter((c) => c.status === "concluded");
    }

    // Apply sort
    switch (sort) {
      case "active":
        result.sort((a, b) => {
          // Active first, then by most recent
          if (a.status === "active" && b.status !== "active") return -1;
          if (b.status === "active" && a.status !== "active") return 1;
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        break;
      case "participants":
        result.sort((a, b) => b.participants.length - a.participants.length);
        break;
      case "recent":
      default:
        result.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }

    return result;
  }, [chats, filter, sort, searchQuery]);

  const activeCount = chats.filter((c) => c.status === "active" || c.status === "paused").length;
  const concludedCount = chats.filter((c) => c.status === "concluded").length;

  return (
    <div className="flex-1 min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-card border-b">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-[24px] font-bold text-foreground">
                Group Discussions
              </h1>
              <p className="text-[13px] mt-0.5 text-muted-foreground/70">
                Multi-agent conversations exploring ideas together
              </p>
            </div>

            <Button
              onClick={() => setShowStartModal(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-[14px] font-semibold shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              New Discussion
            </Button>
          </div>

          {/* Search and filters row */}
          <div className="flex items-center gap-4">
            {/* Search input */}
            <div className="relative flex-1 max-w-md">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <Input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search discussions..."
                className="pl-10 rounded-xl text-[13px]"
              />
            </div>

            {/* Filter tabs */}
            <div className="flex items-center rounded-xl p-1 bg-muted">
              {[
                { key: "all", label: "All", count: chats.length },
                { key: "active", label: "Active", count: activeCount },
                { key: "concluded", label: "Concluded", count: concludedCount },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setFilter(tab.key as FilterType)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all",
                    filter === tab.key
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {tab.key === "active" && (
                    <span className="h-1.5 w-1.5 rounded-full animate-pulse bg-success" />
                  )}
                  {tab.label}
                  <span
                    className={cn(
                      "data-mono text-[10px] px-1.5 py-0.5 rounded-full",
                      filter === tab.key
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {tab.count}
                  </span>
                </button>
              ))}
            </div>

            {/* Sort dropdown */}
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortType)}
              className="px-3 py-2 rounded-xl text-[12px] font-medium bg-background border cursor-pointer min-w-[120px]"
            >
              <option value="recent">Most Recent</option>
              <option value="active">Active First</option>
              <option value="participants">Most Agents</option>
            </select>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="p-6">
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card key={i} className="p-5">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1">
                    <Skeleton className="h-4 w-16 mb-2" />
                    <Skeleton className="h-5 w-full mb-1" />
                    <Skeleton className="h-5 w-3/4" />
                  </div>
                  <div className="flex -space-x-2">
                    {[1, 2, 3].map((j) => (
                      <Skeleton key={j} className="h-6 w-6 rounded-xl" />
                    ))}
                  </div>
                </div>
                <Skeleton className="h-1.5 w-full rounded-full mb-3" />
                <div className="flex gap-4">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-3 w-16" />
                </div>
              </Card>
            ))}
          </div>
        ) : processedChats.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            {chats.length === 0 ? (
              // No chats at all
              <>
                <div className="h-20 w-20 rounded-2xl flex items-center justify-center mb-5 animate-float bg-primary/10">
                  <svg
                    className="h-10 w-10 text-primary"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155"
                    />
                  </svg>
                </div>
                <h3 className="text-[18px] font-bold mb-2 text-foreground">
                  Start Your First Discussion
                </h3>
                <p className="text-[14px] mb-6 text-center max-w-md leading-relaxed text-muted-foreground">
                  Bring together AI agents to explore ideas, debate topics, and discover
                  insights through collaborative multi-agent conversation.
                </p>
                <Button
                  onClick={() => setShowStartModal(true)}
                  className="px-6 py-3 rounded-xl text-[14px] font-semibold flex items-center gap-2"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                  New Discussion
                </Button>
              </>
            ) : (
              // No results for current filter/search
              <>
                <div className="h-16 w-16 rounded-2xl flex items-center justify-center mb-4 bg-muted">
                  <svg
                    className="h-8 w-8 text-muted-foreground"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
                    />
                  </svg>
                </div>
                <h3 className="text-[16px] font-semibold mb-1 text-foreground">
                  No discussions found
                </h3>
                <p className="text-[13px] text-center text-muted-foreground">
                  Try adjusting your search or filter criteria
                </p>
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="mt-3 text-[13px] font-medium text-primary hover:underline"
                  >
                    Clear search
                  </button>
                )}
              </>
            )}
          </div>
        ) : (
          <>
            {/* Results count */}
            <div className="mb-4 text-[12px] text-muted-foreground">
              {processedChats.length} discussion{processedChats.length !== 1 ? "s" : ""}
              {searchQuery && ` matching "${searchQuery}"`}
            </div>

            {/* Chat grid */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 stagger">
              {processedChats.map((chat) => (
                <ChatCard key={chat.id} chat={chat} />
              ))}
            </div>
          </>
        )}
      </main>

      {/* Start Chat Modal */}
      <StartChatModal
        isOpen={showStartModal}
        onClose={() => setShowStartModal(false)}
        onStart={handleStartChat}
      />
    </div>
  );
}
