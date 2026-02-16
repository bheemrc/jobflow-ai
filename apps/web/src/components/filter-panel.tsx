import { JobFilters } from "@/lib/job-filters";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface FilterPanelProps {
  filters: JobFilters;
  availableJobTypes: string[];
  availableLocations: string[];
  onFilterChange: (filters: JobFilters) => void;
  refineQuery: string;
  onRefineChange: (query: string) => void;
  hasActive: boolean;
  onClear: () => void;
}

export default function FilterPanel({
  filters,
  availableJobTypes,
  availableLocations,
  onFilterChange,
  refineQuery,
  onRefineChange,
  hasActive,
  onClear,
}: FilterPanelProps) {
  function toggleJobType(type: string) {
    const jobTypes = filters.jobTypes.includes(type)
      ? filters.jobTypes.filter((t) => t !== type)
      : [...filters.jobTypes, type];
    onFilterChange({ ...filters, jobTypes });
  }

  function toggleLocation(loc: string) {
    const locations = filters.locations.includes(loc)
      ? filters.locations.filter((l) => l !== loc)
      : [...filters.locations, loc];
    onFilterChange({ ...filters, locations });
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-6 pb-3">
      {/* Refine search input */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Refine results..."
          value={refineQuery}
          onChange={(e) => onRefineChange(e.target.value)}
          className="h-7 w-36 rounded-full pl-7 pr-2.5 text-[11px]"
        />
      </div>

      <Separator orientation="vertical" className="h-3.5" />

      {/* Checkbox toggles */}
      <label className="flex items-center gap-1.5 text-[11px] cursor-pointer select-none text-muted-foreground">
        <Checkbox
          checked={filters.remoteOnly}
          onCheckedChange={(checked) => onFilterChange({ ...filters, remoteOnly: checked === true })}
          className="h-3 w-3"
        />
        Remote
      </label>
      <label className="flex items-center gap-1.5 text-[11px] cursor-pointer select-none text-muted-foreground">
        <Checkbox
          checked={filters.hasSalary}
          onCheckedChange={(checked) => onFilterChange({ ...filters, hasSalary: checked === true })}
          className="h-3 w-3"
        />
        Has salary
      </label>

      {/* Job type chips */}
      {availableJobTypes.length > 0 && (
        <Separator orientation="vertical" className="h-3.5" />
      )}
      {availableJobTypes.map((type) => (
        <button
          key={type}
          onClick={() => toggleJobType(type)}
          className={cn(
            "rounded-full px-2 py-0.5 text-[10px] font-semibold transition-all duration-200",
            filters.jobTypes.includes(type)
              ? "bg-primary text-primary-foreground"
              : "bg-accent text-muted-foreground hover:text-foreground"
          )}
        >
          {type}
        </button>
      ))}

      {/* Location chips */}
      {availableLocations.length > 0 && (
        <Separator orientation="vertical" className="h-3.5" />
      )}
      {availableLocations.map((loc) => (
        <button
          key={loc}
          onClick={() => toggleLocation(loc)}
          className={cn(
            "rounded-full px-2 py-0.5 text-[10px] font-semibold transition-all duration-200",
            filters.locations.includes(loc)
              ? "bg-primary text-primary-foreground"
              : "bg-accent text-muted-foreground hover:text-foreground"
          )}
        >
          {loc}
        </button>
      ))}

      {/* Clear filters */}
      {hasActive && (
        <>
          <Separator orientation="vertical" className="h-3.5" />
          <button
            onClick={onClear}
            className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-destructive transition-colors duration-200 hover:text-destructive/80"
          >
            Clear filters
          </button>
        </>
      )}
    </div>
  );
}
