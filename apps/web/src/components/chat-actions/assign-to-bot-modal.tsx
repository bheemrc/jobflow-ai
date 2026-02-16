"use client";

import { useState, useEffect } from "react";
import { Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";

interface BotState {
  name: string;
  display_name: string;
  description?: string;
  status: string;
  enabled: boolean;
}

interface AssignToBotModalProps {
  content: string;
  onClose: () => void;
}

const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "secondary" | "destructive"> = {
  waiting: "success",
  scheduled: "success",
  running: "info",
  paused: "warning",
  stopped: "secondary",
  errored: "destructive",
  disabled: "secondary",
};

export default function AssignToBotModal({ content, onClose }: AssignToBotModalProps) {
  const [bots, setBots] = useState<BotState[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    fetch("/api/ai/bots")
      .then((r) => r.json())
      .then((data) => setBots(data.bots || []))
      .catch(() => setBots([]))
      .finally(() => setLoading(false));
  }, []);

  async function handleRun() {
    if (!selected) return;
    setRunning(true);
    setResult(null);
    try {
      const res = await fetch(`/api/ai/bots/${selected}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ context: content }),
      });
      if (res.status === 429) {
        const data = await res.json().catch(() => ({}));
        setResult({ ok: false, message: data.detail || "Rate limited. Try again shortly." });
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Failed (${res.status})`);
      }
      setResult({ ok: true, message: "Bot started!" });
      setTimeout(onClose, 1500);
    } catch (e) {
      setResult({ ok: false, message: e instanceof Error ? e.message : "Failed to start bot" });
    } finally {
      setRunning(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">Assign to Bot</DialogTitle>
          <DialogDescription className="sr-only">Choose a bot to assign this content to</DialogDescription>
        </DialogHeader>

        <div className="max-h-64 overflow-y-auto space-y-1.5">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
            </div>
          ) : bots.length === 0 ? (
            <p className="text-xs text-center py-6 text-muted-foreground">No bots available</p>
          ) : (
            bots.map((bot) => (
              <button
                key={bot.name}
                onClick={() => setSelected(bot.name)}
                className={cn(
                  "w-full text-left rounded-xl px-4 py-3 transition-all border",
                  selected === bot.name
                    ? "bg-primary/10 border-primary/30"
                    : "bg-card border-border hover:border-primary/20"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">
                    {bot.display_name}
                  </span>
                  <Badge variant={STATUS_VARIANT[bot.status] || "secondary"} className="text-[10px]">
                    {bot.status}
                  </Badge>
                </div>
                {bot.description && (
                  <p className="text-[11px] mt-0.5 line-clamp-1 text-muted-foreground">
                    {bot.description}
                  </p>
                )}
              </button>
            ))
          )}
        </div>

        {result && (
          <p className={cn("text-xs", result.ok ? "text-success" : "text-destructive")}>
            {result.message}
          </p>
        )}

        <DialogFooter className="pt-1">
          <Button variant="ghost" size="sm" onClick={onClose} className="text-xs">
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleRun}
            disabled={!selected || running || result?.ok === true}
            className="text-xs"
          >
            {result?.ok ? "Started!" : running ? "Starting..." : "Run"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
