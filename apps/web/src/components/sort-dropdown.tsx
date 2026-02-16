import { SortOption } from "@/lib/job-sorting";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SortDropdownProps {
  value: SortOption;
  onChange: (value: SortOption) => void;
}

export default function SortDropdown({ value, onChange }: SortDropdownProps) {
  return (
    <div className="flex items-center gap-1.5">
      <Label htmlFor="sort-by" className="text-[11px] font-medium text-muted-foreground">
        Sort:
      </Label>
      <Select value={value} onValueChange={(v) => onChange(v as SortOption)}>
        <SelectTrigger className="h-8 w-[140px] rounded-lg text-[11px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="relevance">Relevance</SelectItem>
          <SelectItem value="date">Date (newest)</SelectItem>
          <SelectItem value="salary">Salary (high)</SelectItem>
          <SelectItem value="location">Location (A-Z)</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
