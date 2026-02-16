"use client";

import { useState, useEffect, useCallback } from "react";
import { ReactionCard } from "@/components/katalyst/reaction-card";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Reaction } from "@/lib/use-katalyst-events";

type FilterStatus = "all" | "active" | "completed" | "paused" | "abandoned";

export default function KatalystPage() {
  const [reactions, setReactions] = useState<Reaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [goal, setGoal] = useState("");
  const [spawning, setSpawning] = useState(false);

  const fetchReactions = useCallback(async () => {
    try {
      const qs = filter !== "all" ? `?status=${filter}` : "";
      const r = await fetch(`/api/ai/katalyst/reactions${qs}`);
      const data = await r.json();
      if (data?.reactions) setReactions(data.reactions);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchReactions();
  }, [fetchReactions]);

  const handleSpawn = useCallback(async () => {
    const trimmed = goal.trim();
    if (!trimmed) return;
    setSpawning(true);
    try {
      const r = await fetch("/api/ai/katalyst/reactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: trimmed }),
      });
      if (r.ok) {
        setGoal("");
        await fetchReactions();
      }
    } catch {
      // ignore
    } finally {
      setSpawning(false);
    }
  }, [goal, fetchReactions]);

  const filters: { key: FilterStatus; label: string }[] = [
    { key: "all", label: "All" },
    { key: "active", label: "Active" },
    { key: "completed", label: "Completed" },
    { key: "paused", label: "Paused" },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[860px] mx-auto px-4 pt-6 pb-16">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-[22px] font-bold mb-1 text-foreground">
            Katalyst
          </h1>
          <p className="text-[13px] text-muted-foreground">
            Post a goal and let agents decompose it into workstreams, produce artifacts, and ask for your input when needed.
          </p>
        </div>

        {/* Goal input */}
        <Card className="p-4 mb-6">
          <Textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Describe your goal... e.g. 'Prepare for a senior frontend engineer role at Stripe'"
            className="w-full resize-none text-[14px] min-h-[60px] border-0 bg-transparent p-0 focus-visible:ring-0"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleSpawn();
              }
            }}
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-[10px] text-muted-foreground">
              Cmd+Enter to launch
            </span>
            <Button
              onClick={handleSpawn}
              disabled={spawning || !goal.trim()}
              className="rounded-xl px-5 py-2 text-[13px]"
            >
              {spawning ? "Launching..." : "Launch Reaction"}
            </Button>
          </div>
        </Card>

        {/* Filters */}
        <div className="flex items-center gap-1.5 mb-4">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors",
                filter === f.key
                  ? "bg-primary/10 text-primary"
                  : "bg-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Reactions list */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="rounded-2xl h-[120px] w-full" />
            ))}
          </div>
        ) : reactions.length === 0 ? (
          <Card className="p-12 text-center">
            <p className="text-[14px] mb-1 text-muted-foreground">
              No reactions yet
            </p>
            <p className="text-[12px] text-muted-foreground">
              Describe a goal above to spawn your first reaction.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {reactions.map((r) => (
              <ReactionCard key={r.id} reaction={r} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
