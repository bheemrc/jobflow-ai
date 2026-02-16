"use client";

import { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const tabs: { label: string; value: string }[] = [
  { label: "All", value: "all" },
  { label: "Saved", value: "saved" },
  { label: "Applied", value: "applied" },
  { label: "Interview", value: "interview" },
  { label: "Offer", value: "offer" },
  { label: "Rejected", value: "rejected" },
];

interface StatusFilterProps {
  current: string;
  onChange: (status: JobStatus | "all") => void;
}

export default function StatusFilter({ current, onChange }: StatusFilterProps) {
  return (
    <div className="inline-flex rounded-xl bg-muted p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value as JobStatus | "all")}
          className={cn(
            "rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all duration-200",
            current === tab.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
