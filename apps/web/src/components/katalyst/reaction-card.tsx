"use client";

import { memo } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Reaction } from "@/lib/use-katalyst-events";

const STATUS_VARIANT: Record<string, "info" | "success" | "warning" | "destructive" | "secondary"> = {
  planning: "info",
  active: "success",
  paused: "warning",
  completed: "success",
  abandoned: "destructive",
};

export const ReactionCard = memo(function ReactionCard({
  reaction,
}: {
  reaction: Reaction;
}) {
  const variant = STATUS_VARIANT[reaction.status] || "info";
  const wsCount = reaction.workstreams?.length || 0;
  const completedWs = reaction.workstreams?.filter((w) => w.status === "completed").length || 0;
  const blockerCount = reaction.blockers?.filter((b) => !b.resolved_at).length || 0;
  const progress = wsCount > 0 ? Math.round((completedWs / wsCount) * 100) : 0;

  return (
    <Link href={`/katalyst/${reaction.id}`}>
      <Card className="p-5 transition-all duration-200 cursor-pointer group hover:shadow-md hover:border-border">
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3 className="text-[15px] font-semibold leading-snug line-clamp-2 text-foreground">
            {reaction.goal}
          </h3>
          <Badge variant={variant} className="shrink-0 uppercase tracking-wider text-[10px]">
            {reaction.status}
          </Badge>
        </div>

        {/* Progress bar */}
        <div className="mb-3">
          <div className="h-1.5 rounded-full overflow-hidden bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                reaction.status === "completed" ? "bg-success" : "bg-primary"
              )}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
          <span>{wsCount} workstream{wsCount !== 1 ? "s" : ""}</span>
          <span>{completedWs}/{wsCount} done</span>
          {blockerCount > 0 && (
            <span className="text-warning">
              {blockerCount} blocker{blockerCount !== 1 ? "s" : ""}
            </span>
          )}
          <span className="ml-auto">
            {reaction.lead_agent}
          </span>
          <span>{new Date(reaction.created_at).toLocaleDateString()}</span>
        </div>
      </Card>
    </Link>
  );
});
