"use client";

import { cn } from "@/lib/utils";
import type { BuilderInfo } from "@/lib/use-timeline-events";

interface BuilderProgressProps {
  builders: BuilderInfo[];
}

export function BuilderProgress({ builders }: BuilderProgressProps) {
  if (!builders || builders.length === 0) return null;

  return (
    <div className="space-y-2 mt-3">
      {builders.map((b) => (
        <div
          key={b.builderId}
          className={cn(
            "rounded-xl px-3 py-2.5 animate-fade-in border",
            b.complete
              ? "bg-sky-400/[0.08] border-sky-400/25"
              : "bg-sky-400/[0.05] border-sky-400/15"
          )}
        >
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[13px]">
                {b.complete ? "\u{1F4D6}" : "\u{1F528}"}
              </span>
              <span className="text-[12px] font-semibold truncate text-sky-400">
                {b.title}
              </span>
            </div>
            {b.complete && b.materialId ? (
              <a
                href={`/prep/materials/${b.materialId}`}
                className="shrink-0 px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-colors bg-sky-400/15 text-sky-400 hover:bg-sky-400/25"
              >
                View Tutorial
              </a>
            ) : (
              <span className="text-[10px] font-medium data-mono shrink-0 text-sky-400/70">
                {b.percent}%
              </span>
            )}
          </div>

          {/* Progress bar */}
          {!b.complete && (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-sky-400/10">
                <div
                  className="h-full rounded-full transition-all duration-500 bg-gradient-to-r from-sky-400 to-indigo-400 shadow-[0_0_8px_rgba(56,189,248,0.3)]"
                  style={{ width: `${b.percent}%` }}
                />
              </div>
              <span className="text-[9px] font-medium shrink-0 text-sky-400/50">
                {b.stage}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
