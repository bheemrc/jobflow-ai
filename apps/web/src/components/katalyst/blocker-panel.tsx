"use client";

import { memo, useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { Blocker } from "@/lib/use-katalyst-events";

const SEVERITY_VARIANT: Record<string, "info" | "warning" | "destructive"> = {
  low: "info",
  medium: "warning",
  high: "destructive",
};

export const BlockerPanel = memo(function BlockerPanel({
  blocker,
  onResolve,
}: {
  blocker: Blocker;
  onResolve?: (blockerId: number, resolution: string) => void;
}) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [customResolution, setCustomResolution] = useState("");
  const [resolving, setResolving] = useState(false);

  const sevVariant = SEVERITY_VARIANT[blocker.severity] || "warning";
  const isResolved = !!blocker.resolved_at;

  const handleResolve = useCallback(async () => {
    const resolution = selectedOption || customResolution.trim();
    if (!resolution || !onResolve) return;
    setResolving(true);
    try {
      await onResolve(blocker.id, resolution);
    } finally {
      setResolving(false);
    }
  }, [blocker.id, selectedOption, customResolution, onResolve]);

  return (
    <div
      className={cn(
        "rounded-xl p-4 transition-all bg-card border",
        isResolved && "opacity-60"
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h4
          className={cn(
            "text-[13px] font-semibold",
            isResolved ? "text-muted-foreground" : "text-foreground"
          )}
        >
          {blocker.title}
        </h4>
        <Badge variant={sevVariant} className="shrink-0 text-[9px] uppercase tracking-wider">
          {blocker.severity}
        </Badge>
      </div>

      {blocker.description && (
        <p className="text-[11px] mb-3 text-muted-foreground">
          {blocker.description}
        </p>
      )}

      {/* Confidence bar */}
      {blocker.auto_resolve_confidence > 0 && !isResolved && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-[10px] mb-1 text-muted-foreground">
            <span>AI confidence</span>
            <span>{Math.round(blocker.auto_resolve_confidence * 100)}%</span>
          </div>
          <div className="h-1 rounded-full overflow-hidden bg-muted">
            <div
              className={cn(
                "h-full rounded-full",
                blocker.auto_resolve_confidence >= 0.8 ? "bg-success" : "bg-warning"
              )}
              style={{
                width: `${blocker.auto_resolve_confidence * 100}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Options */}
      {!isResolved && blocker.options.length > 0 && (
        <div className="space-y-1.5 mb-3">
          {blocker.options.map((opt, i) => (
            <button
              key={i}
              onClick={() => setSelectedOption(opt.label)}
              className={cn(
                "w-full text-left rounded-lg px-3 py-2 transition-all text-[12px] border",
                selectedOption === opt.label
                  ? "bg-primary/10 border-primary text-primary"
                  : "bg-muted/50 border-border text-muted-foreground"
              )}
            >
              <span className="font-medium">{opt.label}</span>
              {opt.description && (
                <span className="block text-[10px] mt-0.5 text-muted-foreground">
                  {opt.description}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Custom resolution input */}
      {!isResolved && (
        <div className="flex gap-2">
          <Input
            type="text"
            value={customResolution}
            onChange={(e) => {
              setCustomResolution(e.target.value);
              setSelectedOption(null);
            }}
            placeholder="Or type a custom resolution..."
            className="flex-1 rounded-lg text-[12px]"
          />
          <Button
            onClick={handleResolve}
            disabled={resolving || (!selectedOption && !customResolution.trim())}
            size="sm"
            className="rounded-lg px-4 text-[12px]"
          >
            {resolving ? "..." : "Resolve"}
          </Button>
        </div>
      )}

      {/* Resolution display */}
      {isResolved && (
        <div className="rounded-lg px-3 py-2 text-[11px] mt-2 bg-muted/50 text-muted-foreground">
          <span className="font-medium text-success">Resolved: </span>
          {blocker.resolution}
          <span className="block text-[10px] mt-0.5 text-muted-foreground">
            by {blocker.resolved_by} · {blocker.resolved_at ? new Date(blocker.resolved_at).toLocaleString() : ""}
          </span>
        </div>
      )}

      {/* Meta */}
      <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
        <span>{blocker.agent}</span>
        <span>·</span>
        <span>{new Date(blocker.created_at).toLocaleString()}</span>
      </div>
    </div>
  );
});
