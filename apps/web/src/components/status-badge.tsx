import { JobStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const variantMap: Record<JobStatus, { variant: "secondary" | "info" | "success" | "warning" | "destructive"; dotClass: string }> = {
  saved: { variant: "secondary", dotClass: "bg-muted-foreground" },
  applied: { variant: "info", dotClass: "bg-primary" },
  interview: { variant: "success", dotClass: "bg-success" },
  offer: { variant: "warning", dotClass: "bg-warning" },
  rejected: { variant: "destructive", dotClass: "bg-destructive" },
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  const s = variantMap[status];
  return (
    <Badge variant={s.variant} className="capitalize gap-1.5">
      <span className={cn("h-1.5 w-1.5 rounded-full", s.dotClass)} />
      {status}
    </Badge>
  );
}
