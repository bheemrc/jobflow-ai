"use client";

import { useState, useCallback, memo } from "react";
import { cn } from "@/lib/utils";

interface VoteButtonsProps {
  votes: number;
  userVote: 1 | -1 | 0;
  onVote: (direction: 1 | -1) => void;
  compact?: boolean;
}

export const VoteButtons = memo(function VoteButtons({ votes, userVote, onVote, compact = false }: VoteButtonsProps) {
  const [animating, setAnimating] = useState<"up" | "down" | null>(null);

  const formatVotes = (n: number) => {
    if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return n.toString();
  };

  const handleVote = useCallback((dir: 1 | -1) => {
    setAnimating(dir === 1 ? "up" : "down");
    onVote(dir);
    setTimeout(() => setAnimating(null), 300);
  }, [onVote]);

  return (
    <div
      className={cn("flex select-none", compact ? "flex-row items-center gap-1" : "flex-col items-center gap-0")}
    >
      {/* Upvote */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          handleVote(1);
        }}
        className={cn(
          "group p-1 rounded-md transition-all duration-150 hover:bg-orange-500/10 hover:text-orange-500",
          userVote === 1 ? "text-orange-500" : "text-muted-foreground",
          animating === "up" && "scale-130"
        )}
        style={{
          transform: animating === "up" ? "scale(1.3)" : "scale(1)",
          transition: "transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.15s, background 0.15s",
        }}
        title="Upvote"
        aria-label={`Upvote (${userVote === 1 ? "active" : "inactive"})`}
      >
        <svg
          className={compact ? "h-4 w-4" : "h-5 w-5"}
          fill={userVote === 1 ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth={userVote === 1 ? 0 : 2}
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 4l-8 8h5v8h6v-8h5l-8-8z"
          />
        </svg>
      </button>

      {/* Score */}
      <span
        className={cn(
          "font-bold data-mono text-center",
          compact ? "text-[11px] min-w-[24px]" : "text-[12px] min-w-[28px] py-0.5",
          userVote === 1 ? "text-orange-500" : userVote === -1 ? "text-indigo-400" : "text-muted-foreground"
        )}
      >
        {formatVotes(votes)}
      </span>

      {/* Downvote */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          handleVote(-1);
        }}
        className={cn(
          "group p-1 rounded-md transition-all duration-150 hover:bg-indigo-400/10 hover:text-indigo-400",
          userVote === -1 ? "text-indigo-400" : "text-muted-foreground"
        )}
        style={{
          transform: animating === "down" ? "scale(1.3)" : "scale(1)",
          transition: "transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.15s, background 0.15s",
        }}
        title="Downvote"
        aria-label={`Downvote (${userVote === -1 ? "active" : "inactive"})`}
      >
        <svg
          className={compact ? "h-4 w-4" : "h-5 w-5"}
          fill={userVote === -1 ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth={userVote === -1 ? 0 : 2}
          viewBox="0 0 24 24"
          style={{ transform: "rotate(180deg)" }}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 4l-8 8h5v8h6v-8h5l-8-8z"
          />
        </svg>
      </button>
    </div>
  );
});
