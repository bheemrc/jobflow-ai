"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface ShortcutHelpProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS = [
  { key: "j", label: "Next signal" },
  { key: "k", label: "Previous signal" },
  { key: "a", label: "Upvote focused signal" },
  { key: "z", label: "Downvote focused signal" },
  { key: "r", label: "Reply to focused signal" },
  { key: "/", label: "Focus search" },
  { key: "c", label: "Focus compose" },
  { key: "?", label: "Toggle this help" },
  { key: "Esc", label: "Close / blur" },
];

export function ShortcutHelp({ open, onClose }: ShortcutHelpProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <Card
        className="relative w-[340px] rounded-2xl overflow-hidden animate-scale-in shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 flex items-center justify-between border-b">
          <div className="flex items-center gap-2">
            <span className="text-[14px]">&#x2328;&#xFE0F;</span>
            <h3 className="text-[14px] font-bold text-foreground">
              Keyboard Shortcuts
            </h3>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onClose}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </Button>
        </div>

        <div className="px-5 py-4 space-y-2">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="flex items-center justify-between py-1">
              <span className="text-[12px] text-muted-foreground">
                {s.label}
              </span>
              <kbd className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-muted border border-border text-foreground shadow-sm">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>

        <Separator />
        <div className="px-5 py-3 text-center">
          <span className="text-[10px] data-mono text-muted-foreground">
            Press <kbd className="px-1 py-0.5 rounded text-[9px] font-mono bg-muted border border-border">?</kbd> to toggle
          </span>
        </div>
      </Card>
    </div>
  );
}
