"use client";

import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";

interface RelatedSearchesProps {
  suggestions: string[];
  onSearch: (term: string) => void;
}

export default function RelatedSearches({ suggestions, onSearch }: RelatedSearchesProps) {
  if (suggestions.length === 0) return null;

  return (
    <div className="mt-6">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Related searches</p>
      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((term) => (
          <Button
            key={term}
            variant="ghost"
            size="sm"
            onClick={() => onSearch(term)}
            className="gap-1 rounded-full px-3 py-1.5 text-[11px] font-medium h-auto"
          >
            <Search className="h-3 w-3 text-muted-foreground" />
            {term}
          </Button>
        ))}
      </div>
    </div>
  );
}
