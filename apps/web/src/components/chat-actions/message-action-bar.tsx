"use client";

import { Bookmark, Play, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface MessageActionBarProps {
  content: string;
  onAddToPrep: () => void;
  onAssignToBot: () => void;
  onNewBot: () => void;
}

export default function MessageActionBar({
  content,
  onAddToPrep,
  onAssignToBot,
  onNewBot,
}: MessageActionBarProps) {
  return (
    <div className="flex items-center gap-1 mt-1">
      <Button
        variant="ghost"
        size="sm"
        onClick={onAddToPrep}
        className="h-auto gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
        title="Save as prep material"
      >
        <Bookmark className="h-3 w-3" />
        Prep
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onAssignToBot}
        className="h-auto gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
        title="Assign to an existing bot"
      >
        <Play className="h-3 w-3" />
        Assign
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onNewBot}
        className="h-auto gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-muted-foreground"
        title="Create a new bot from this message"
      >
        <Plus className="h-3 w-3" />
        New Bot
      </Button>
    </div>
  );
}
