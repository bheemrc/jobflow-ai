"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";

interface ToolInfo {
  name: string;
  description: string;
  category: string;
}

interface AssignToNewBotModalProps {
  content: string;
  onClose: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  resume: "text-purple-400",
  jobs: "text-blue-400",
  research: "text-yellow-400",
  leetcode: "text-orange-400",
  integrations: "text-pink-400",
  prep: "text-green-400",
  bots: "text-cyan-400",
  journal: "text-violet-400",
  other: "text-slate-400",
};

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s_]/g, "")
    .trim()
    .replace(/\s+/g, "_")
    .slice(0, 40);
}

export default function AssignToNewBotModal({ content, onClose }: AssignToNewBotModalProps) {
  const autoSlug = slugify(content.slice(0, 50)) || "custom_bot";
  const autoDisplay = content.replace(/[#*_\n]/g, " ").trim().slice(0, 50) || "Custom Bot";

  const [name, setName] = useState(autoSlug);
  const [displayName, setDisplayName] = useState(autoDisplay);
  const [prompt, setPrompt] = useState(content.slice(0, 5000));
  const [model, setModel] = useState<"fast" | "default" | "strong">("default");
  const [scheduleType, setScheduleType] = useState<"interval" | "cron">("interval");
  const [scheduleHours, setScheduleHours] = useState(6);
  const [scheduleHour, setScheduleHour] = useState(9);
  const [scheduleMinute, setScheduleMinute] = useState(0);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [runImmediately, setRunImmediately] = useState(true);
  const [allTools, setAllTools] = useState<ToolInfo[]>([]);
  const [creating, setCreating] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    fetch("/api/ai/bots/tools")
      .then((r) => r.json())
      .then((data) => setAllTools(data.tools || []))
      .catch(() => {});
  }, []);

  function toggleTool(toolName: string) {
    setSelectedTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName]
    );
  }

  const toolsByCategory = allTools.reduce<Record<string, ToolInfo[]>>((acc, t) => {
    (acc[t.category] = acc[t.category] || []).push(t);
    return acc;
  }, {});

  async function handleCreate() {
    setCreating(true);
    setResult(null);
    try {
      // Validate name format
      if (!/^[a-z][a-z0-9_]{1,48}$/.test(name)) {
        setResult({ ok: false, message: "Name must be lowercase letters, numbers, underscores (2-49 chars, start with letter)" });
        setCreating(false);
        return;
      }

      const createRes = await fetch("/api/ai/bots/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          display_name: displayName,
          prompt,
          model,
          tools: selectedTools,
          schedule_type: scheduleType,
          schedule_hours: scheduleType === "interval" ? scheduleHours : undefined,
          schedule_hour: scheduleType === "cron" ? scheduleHour : undefined,
          schedule_minute: scheduleType === "cron" ? scheduleMinute : undefined,
        }),
      });

      if (!createRes.ok) {
        const data = await createRes.json().catch(() => ({}));
        throw new Error(data.detail || `Create failed (${createRes.status})`);
      }

      if (runImmediately) {
        const startRes = await fetch(`/api/ai/bots/${name}/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ context: content }),
        });
        if (startRes.status === 429) {
          setResult({ ok: true, message: "Bot created! (Run skipped — rate limited)" });
        } else if (!startRes.ok) {
          setResult({ ok: true, message: "Bot created! (Auto-run failed)" });
        } else {
          setResult({ ok: true, message: "Bot created and started!" });
        }
      } else {
        setResult({ ok: true, message: "Bot created!" });
      }
      setTimeout(onClose, 1500);
    } catch (e) {
      setResult({ ok: false, message: e instanceof Error ? e.message : "Create failed" });
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-sm">Create New Bot</DialogTitle>
          <DialogDescription className="sr-only">Create and configure a new bot</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {/* Name & Display Name */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[11px] mb-1 block">Name (slug)</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                className="rounded-lg text-sm font-mono"
                maxLength={49}
              />
            </div>
            <div>
              <Label className="text-[11px] mb-1 block">Display Name</Label>
              <Input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="rounded-lg text-sm"
                maxLength={60}
              />
            </div>
          </div>

          {/* Prompt */}
          <div>
            <Label className="text-[11px] mb-1 block">Prompt</Label>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="rounded-lg text-sm resize-none"
              rows={4}
              maxLength={10000}
            />
          </div>

          {/* Tools */}
          <div>
            <Label className="text-[11px] mb-1.5 block">
              Tools {selectedTools.length > 0 && <span className="text-primary">({selectedTools.length})</span>}
            </Label>
            <div className="space-y-2 max-h-40 overflow-y-auto rounded-lg border p-2 bg-card">
              {Object.entries(toolsByCategory).map(([cat, tools]) => (
                <div key={cat}>
                  <div className={cn("text-[10px] font-semibold uppercase mb-1", CATEGORY_COLORS[cat] || "text-muted-foreground")}>
                    {cat}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {tools.map((tool) => (
                      <button
                        key={tool.name}
                        onClick={() => toggleTool(tool.name)}
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors border",
                          selectedTools.includes(tool.name)
                            ? "bg-primary/10 text-primary border-primary/30"
                            : "bg-background text-muted-foreground border-border"
                        )}
                        title={tool.description}
                      >
                        {tool.name.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Model */}
          <div>
            <Label className="text-[11px] mb-1.5 block">Model</Label>
            <div className="flex gap-1.5">
              {(["fast", "default", "strong"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setModel(m)}
                  className={cn(
                    "flex-1 rounded-lg px-3 py-1.5 text-[11px] font-medium transition-colors border",
                    model === m
                      ? "bg-primary/10 text-primary border-primary/30"
                      : "bg-card text-muted-foreground border-border"
                  )}
                >
                  {m === "fast" ? "Fast" : m === "default" ? "Balanced" : "Strong"}
                </button>
              ))}
            </div>
          </div>

          {/* Schedule */}
          <div>
            <Label className="text-[11px] mb-1.5 block">Schedule</Label>
            <div className="flex gap-2 items-center">
              <div className="flex gap-1">
                <button
                  onClick={() => setScheduleType("interval")}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-[11px] font-medium transition-colors border",
                    scheduleType === "interval"
                      ? "bg-primary/10 text-primary border-primary/30"
                      : "bg-card text-muted-foreground border-border"
                  )}
                >
                  Interval
                </button>
                <button
                  onClick={() => setScheduleType("cron")}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-[11px] font-medium transition-colors border",
                    scheduleType === "cron"
                      ? "bg-primary/10 text-primary border-primary/30"
                      : "bg-card text-muted-foreground border-border"
                  )}
                >
                  Daily
                </button>
              </div>
              {scheduleType === "interval" ? (
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-muted-foreground">Every</span>
                  <Input
                    type="number"
                    value={scheduleHours}
                    onChange={(e) => setScheduleHours(Math.max(1, Math.min(168, Number(e.target.value) || 1)))}
                    className="w-14 rounded-lg px-2 py-1.5 text-sm text-center h-auto"
                    min={1}
                    max={168}
                  />
                  <span className="text-[11px] text-muted-foreground">hours</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-muted-foreground">At</span>
                  <Input
                    type="number"
                    value={scheduleHour}
                    onChange={(e) => setScheduleHour(Math.max(0, Math.min(23, Number(e.target.value) || 0)))}
                    className="w-12 rounded-lg px-2 py-1.5 text-sm text-center h-auto"
                    min={0}
                    max={23}
                  />
                  <span className="text-[11px] text-muted-foreground">:</span>
                  <Input
                    type="number"
                    value={scheduleMinute}
                    onChange={(e) => setScheduleMinute(Math.max(0, Math.min(59, Number(e.target.value) || 0)))}
                    className="w-12 rounded-lg px-2 py-1.5 text-sm text-center h-auto"
                    min={0}
                    max={59}
                  />
                  <span className="text-[11px] text-muted-foreground">UTC</span>
                </div>
              )}
            </div>
          </div>

          {/* Run Immediately */}
          <label className="flex items-center gap-2 cursor-pointer">
            <Checkbox
              checked={runImmediately}
              onCheckedChange={(checked) => setRunImmediately(checked === true)}
            />
            <span className="text-[11px] font-medium text-muted-foreground">
              Run immediately with message as context
            </span>
          </label>
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
            onClick={handleCreate}
            disabled={creating || result?.ok === true || !name.trim() || !displayName.trim()}
            className="text-xs"
          >
            {result?.ok ? "Created!" : creating ? "Creating..." : "Create Bot"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
