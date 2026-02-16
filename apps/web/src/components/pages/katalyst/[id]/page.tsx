"use client";

import { use, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { useKatalystStream } from "@/lib/use-katalyst-events";
import { WorkstreamCard } from "@/components/katalyst/workstream-card";
import { ArtifactViewer } from "@/components/katalyst/artifact-viewer";
import { BlockerPanel } from "@/components/katalyst/blocker-panel";
import { EventFeed } from "@/components/katalyst/event-feed";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Artifact } from "@/lib/use-katalyst-events";

type Tab = "workstreams" | "artifacts" | "blockers" | "feed";

export default function ReactionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const reactionId = parseInt(id, 10);
  const {
    reaction,
    workstreams,
    artifacts,
    blockers,
    events,
    connected,
    setReaction,
  } = useKatalystStream(reactionId);
  const [activeTab, setActiveTab] = useState<Tab>("workstreams");
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);

  const unresolvedBlockers = useMemo(
    () => blockers.filter((b) => !b.resolved_at),
    [blockers]
  );

  const handleResolveBlocker = useCallback(
    async (blockerId: number, resolution: string) => {
      try {
        const r = await fetch(`/api/ai/katalyst/blockers/${blockerId}/resolve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ resolution }),
        });
        if (!r.ok) return;
        // Optimistic update
        const resolved = await r.json();
        if (resolved) {
          // Will be refreshed via SSE
        }
      } catch {
        // ignore
      }
    },
    []
  );

  const handleStatusChange = useCallback(
    async (newStatus: string) => {
      try {
        const r = await fetch(`/api/ai/katalyst/reactions/${reactionId}/status`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        });
        if (r.ok) {
          const updated = await r.json();
          setReaction(updated);
        }
      } catch {
        // ignore
      }
    },
    [reactionId, setReaction]
  );

  const [executing, setExecuting] = useState(false);
  const handleExecute = useCallback(async () => {
    setExecuting(true);
    try {
      await fetch(`/api/ai/katalyst/reactions/${reactionId}/execute`, { method: "POST" });
      // Execution runs in background — SSE will push updates.
      // Keep button disabled for a few seconds to prevent spam.
      setTimeout(() => setExecuting(false), 5000);
    } catch {
      setExecuting(false);
    }
  }, [reactionId]);

  const handleViewArtifact = useCallback(
    async (artifactId: number) => {
      try {
        const r = await fetch(`/api/ai/katalyst/artifacts/${artifactId}`);
        const data = await r.json();
        if (data?.id) setSelectedArtifact(data);
      } catch {
        // ignore
      }
    },
    []
  );

  if (!reaction) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin mx-auto mb-3" />
          <p className="text-[13px] text-muted-foreground">Loading reaction...</p>
        </div>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "workstreams", label: "Workstreams", count: workstreams.length },
    { key: "artifacts", label: "Artifacts", count: artifacts.length },
    { key: "blockers", label: "Blockers", count: unresolvedBlockers.length },
    { key: "feed", label: "Feed", count: events.length },
  ];

  const totalProgress = workstreams.length > 0
    ? Math.round(workstreams.reduce((sum, w) => sum + w.progress, 0) / workstreams.length)
    : 0;

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[960px] mx-auto px-4 pt-6 pb-16">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-4 text-[12px] text-muted-foreground">
          <Link href="/katalyst" className="hover:underline text-primary">
            Katalyst
          </Link>
          <span>/</span>
          <span>Reaction #{reaction.id}</span>
          <div className="ml-auto flex items-center gap-1.5">
            <div
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                connected ? "bg-success" : "bg-destructive"
              )}
            />
            <span>{connected ? "Live" : "Offline"}</span>
          </div>
        </div>

        {/* Reaction header */}
        <Card className="p-5 mb-5">
          <div className="flex items-start justify-between gap-4 mb-3">
            <h1 className="text-[18px] font-bold leading-snug text-foreground">
              {reaction.goal}
            </h1>
            <div className="flex items-center gap-2 shrink-0">
              {reaction.status === "active" && (
                <>
                  <Button
                    onClick={handleExecute}
                    disabled={executing}
                    size="sm"
                    className="text-[11px]"
                  >
                    {executing ? "Running..." : "Execute"}
                  </Button>
                  <Button
                    onClick={() => handleStatusChange("paused")}
                    variant="outline"
                    size="sm"
                    className="text-[11px] text-warning"
                  >
                    Pause
                  </Button>
                </>
              )}
              {reaction.status === "paused" && (
                <Button
                  onClick={() => handleStatusChange("active")}
                  variant="outline"
                  size="sm"
                  className="text-[11px] text-success"
                >
                  Resume
                </Button>
              )}
              {reaction.status !== "completed" && reaction.status !== "abandoned" && (
                <Button
                  onClick={() => handleStatusChange("abandoned")}
                  variant="outline"
                  size="sm"
                  className="text-[11px] text-destructive"
                >
                  Abandon
                </Button>
              )}
            </div>
          </div>

          {/* Progress */}
          <div className="mb-3">
            <div className="flex items-center justify-between text-[11px] mb-1 text-muted-foreground">
              <span>Overall progress</span>
              <span>{totalProgress}%</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden bg-muted">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-700",
                  reaction.status === "completed" ? "bg-success" : "bg-primary"
                )}
                style={{ width: `${totalProgress}%` }}
              />
            </div>
          </div>

          {/* Meta */}
          <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
            <span>Lead: <span className="text-foreground">{reaction.lead_agent}</span></span>
            <span>{workstreams.length} workstreams</span>
            <span>{artifacts.length} artifacts</span>
            {unresolvedBlockers.length > 0 && (
              <span className="text-warning">{unresolvedBlockers.length} pending blockers</span>
            )}
            <span className="ml-auto">{new Date(reaction.created_at).toLocaleDateString()}</span>
          </div>

          {/* Phases */}
          {reaction.phases.length > 0 && (
            <div className="flex items-center gap-2 mt-3">
              {reaction.phases.map((phase, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-medium",
                    phase.status === "completed"
                      ? "bg-success/10 text-success"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {phase.status === "completed" ? "✓" : `${i + 1}.`} {phase.name}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Tabs */}
        <div className="flex items-center gap-1 mb-4 px-1 border-b">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "relative rounded-t-lg px-4 py-2.5 text-[12px] font-medium transition-colors",
                activeTab === tab.key
                  ? "text-primary bg-card"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
              {tab.count !== undefined && tab.count > 0 && (
                <Badge
                  variant={tab.key === "blockers" && tab.count > 0 ? "warning" : "secondary"}
                  className="ml-1.5 text-[9px] px-1.5 py-0.5"
                >
                  {tab.count}
                </Badge>
              )}
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-2 right-2 h-[2px] rounded-t-full bg-primary" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div>
          {activeTab === "workstreams" && (
            <div className="space-y-2">
              {workstreams.length === 0 ? (
                <EmptyState text="No workstreams yet" />
              ) : (
                workstreams.map((ws) => <WorkstreamCard key={ws.id} workstream={ws} />)
              )}
            </div>
          )}

          {activeTab === "artifacts" && (
            <div className="space-y-3">
              {selectedArtifact ? (
                <div>
                  <button
                    onClick={() => setSelectedArtifact(null)}
                    className="text-[12px] font-medium mb-3 flex items-center gap-1 text-primary"
                  >
                    ← Back to artifacts
                  </button>
                  <ArtifactViewer
                    artifact={selectedArtifact}
                    onVersionSelect={handleViewArtifact}
                  />
                </div>
              ) : artifacts.length === 0 ? (
                <EmptyState text="No artifacts yet" />
              ) : (
                artifacts.map((a) => (
                  <Card
                    key={a.id}
                    className="w-full text-left p-4 transition-all cursor-pointer hover:border-border hover:shadow-sm"
                    onClick={() => handleViewArtifact(a.id)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <h4 className="text-[13px] font-semibold truncate text-foreground">
                          {a.title}
                        </h4>
                        <p className="text-[11px] mt-0.5 text-muted-foreground">
                          {a.agent} · v{a.version} · {a.artifact_type}
                        </p>
                      </div>
                      <Badge variant={a.status === "draft" ? "info" : "success"} className="shrink-0 text-[9px] uppercase">
                        {a.status}
                      </Badge>
                    </div>
                  </Card>
                ))
              )}
            </div>
          )}

          {activeTab === "blockers" && (
            <div className="space-y-2">
              {blockers.length === 0 ? (
                <EmptyState text="No blockers" />
              ) : (
                blockers.map((b) => (
                  <BlockerPanel
                    key={b.id}
                    blocker={b}
                    onResolve={handleResolveBlocker}
                  />
                ))
              )}
            </div>
          )}

          {activeTab === "feed" && <EventFeed events={events} />}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <Card className="p-8 text-center text-[12px] text-muted-foreground">
      {text}
    </Card>
  );
}
