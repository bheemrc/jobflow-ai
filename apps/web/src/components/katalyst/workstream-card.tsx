"use client";

import { memo } from "react";
import { Card } from "@/components/ui/card";
import type { Workstream } from "@/lib/use-katalyst-events";

const STAGE_COLORS: Record<string, string> = {
  pending: "hsl(var(--muted-foreground))",
  research: "#58A6FF",
  drafting: "#A78BFA",
  refining: "#E3B341",
  review: "#F97316",
  completed: "#56D364",
};

const STAGE_LABELS: Record<string, string> = {
  pending: "Queued",
  research: "Researching",
  drafting: "Drafting",
  refining: "Refining",
  review: "In Review",
  completed: "Done",
};

export const WorkstreamCard = memo(function WorkstreamCard({
  workstream,
}: {
  workstream: Workstream;
}) {
  const color = STAGE_COLORS[workstream.status] || "hsl(var(--muted-foreground))";
  const label = STAGE_LABELS[workstream.status] || workstream.status;

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <h4 className="text-[13px] font-semibold truncate text-foreground">
            {workstream.title}
          </h4>
          {workstream.description && (
            <p className="text-[11px] mt-0.5 line-clamp-2 text-muted-foreground">
              {workstream.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color }}
          >
            {label}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-2">
        <div className="h-1 rounded-full overflow-hidden bg-muted">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${workstream.progress}%`, background: color }}
          />
        </div>
      </div>

      {/* Agent + phase */}
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
        <span className="font-medium text-muted-foreground">
          {workstream.agent}
        </span>
        {workstream.phase && (
          <>
            <span>·</span>
            <span>{workstream.phase}</span>
          </>
        )}
        <span className="ml-auto">{workstream.progress}%</span>
      </div>
    </Card>
  );
});
