"use client";

import { memo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Artifact } from "@/lib/use-katalyst-events";

export const ArtifactViewer = memo(function ArtifactViewer({
  artifact,
  onVersionSelect,
}: {
  artifact: Artifact;
  onVersionSelect?: (id: number) => void;
}) {
  const [showVersions, setShowVersions] = useState(false);
  const versions = artifact.versions || [];

  return (
    <div className="rounded-xl overflow-hidden bg-card border">
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between border-b">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[11px] font-mono text-muted-foreground">
            {artifact.artifact_type}
          </span>
          <h4 className="text-[13px] font-semibold truncate text-foreground">
            {artifact.title}
          </h4>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] font-mono text-muted-foreground">
            v{artifact.version}
          </span>
          {versions.length > 1 && (
            <button
              onClick={() => setShowVersions(!showVersions)}
              className={cn(
                "text-[10px] font-medium px-2 py-0.5 rounded-md transition-colors text-primary",
                showVersions ? "bg-primary/10" : "bg-transparent"
              )}
            >
              {showVersions ? "Hide" : `${versions.length} versions`}
            </button>
          )}
          <Badge variant={artifact.status === "draft" ? "info" : "success"} className="text-[9px] uppercase">
            {artifact.status}
          </Badge>
        </div>
      </div>

      {/* Version history */}
      {showVersions && versions.length > 1 && (
        <div className="px-4 py-2 flex flex-wrap gap-1.5 border-b bg-muted/50">
          {versions.map((v) => (
            <button
              key={v.id}
              onClick={() => onVersionSelect?.(v.id)}
              className={cn(
                "px-2 py-0.5 rounded-md text-[10px] font-mono transition-colors",
                v.id === artifact.id
                  ? "bg-primary/10 text-primary"
                  : "bg-transparent text-muted-foreground"
              )}
            >
              v{v.version} — {v.status}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="px-4 py-4 prose-sm max-h-[500px] overflow-y-auto text-muted-foreground">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {artifact.content || "*No content yet*"}
        </ReactMarkdown>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 flex items-center gap-3 text-[10px] border-t text-muted-foreground">
        <span>{artifact.agent}</span>
        <span>·</span>
        <span>{new Date(artifact.created_at).toLocaleString()}</span>
      </div>
    </div>
  );
});
