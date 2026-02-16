"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface MatchScoreBadgeProps {
  score: number;
}

export default function MatchScoreBadge({ score }: MatchScoreBadgeProps) {
  const variant =
    score >= 80
      ? "success"
      : score >= 60
        ? "warning"
        : score >= 40
          ? "warning"
          : "destructive";

  return (
    <Badge
      variant={variant}
      className={cn(
        "font-mono",
        score >= 40 && score < 60 && "bg-orange-500/10 text-orange-500"
      )}
      title={`Match score: ${score}%`}
    >
      {score}% match
    </Badge>
  );
}
