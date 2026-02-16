"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import type { PrepMaterial, PrepMaterialType } from "@/lib/types";
import Markdown from "@/components/markdown";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const TYPE_BADGES: Record<PrepMaterialType, { label: string; variant: "success" | "info" | "warning" | "destructive" | "secondary"; icon: string }> = {
  interview: { label: "Interview Prep", variant: "success", icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" },
  system_design: { label: "System Design", variant: "info", icon: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" },
  leetcode: { label: "LeetCode Plan", variant: "warning", icon: "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" },
  company_research: { label: "Company Research", variant: "secondary", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
  general: { label: "General", variant: "secondary", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  tutorial: { label: "Tutorial", variant: "info", icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" },
};

function extractHeadings(text: string): { id: string; text: string; level: number }[] {
  const headings: { id: string; text: string; level: number }[] = [];
  const lines = text.split("\n");
  for (const line of lines) {
    const match = line.match(/^(#{1,3})\s+(.+)$/);
    if (match) {
      const level = match[1].length;
      const headingText = match[2].replace(/[*_`]/g, "").trim();
      const id = headingText.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
      headings.push({ id, text: headingText, level });
    }
  }
  return headings;
}

function estimateReadTime(text: string): number {
  const words = text.split(/\s+/).length;
  // Code blocks take longer to read
  const codeBlocks = (text.match(/```[\s\S]*?```/g) || []).length;
  return Math.max(1, Math.ceil((words + codeBlocks * 40) / 220));
}

function getMarkdownText(material: PrepMaterial): string | null {
  const content = material.content;
  if (!content || typeof content !== "object") return null;
  if ("text" in content && typeof content.text === "string") return content.text;
  return null;
}

function renderContent(material: PrepMaterial) {
  const content = material.content;
  if (!content || typeof content !== "object") {
    return <p className="text-[13px] leading-relaxed text-muted-foreground">{String(content)}</p>;
  }

  if ("text" in content && typeof content.text === "string") {
    return (
      <div className="article-content">
        <Markdown>{content.text}</Markdown>
      </div>
    );
  }

  const entries = Object.entries(content);
  if (entries.length === 0) return null;

  return (
    <div className="space-y-6">
      {entries.map(([key, value]) => {
        const label = key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
        return (
          <div key={key}>
            <h3 className="text-[14px] font-semibold mb-3 text-foreground">{label}</h3>
            {typeof value === "string" ? (
              <div className="article-content">
                <Markdown>{value}</Markdown>
              </div>
            ) : Array.isArray(value) ? (
              <div className="space-y-2">
                {value.map((item, i) => (
                  <div
                    key={i}
                    className="rounded-xl px-4 py-3 bg-muted"
                  >
                    {typeof item === "string" ? (
                      <p className="text-[13px] leading-relaxed text-muted-foreground">{item}</p>
                    ) : typeof item === "object" && item !== null ? (
                      <div className="space-y-1.5">
                        {Object.entries(item).map(([k, v]) => (
                          <div key={k} className="flex gap-2">
                            <span className="text-[11px] font-medium shrink-0 capitalize text-muted-foreground/70">{k}:</span>
                            <span className="text-[12px] text-muted-foreground">
                              {typeof v === "string" ? v : JSON.stringify(v)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[13px] text-muted-foreground">{JSON.stringify(item)}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : typeof value === "object" && value !== null ? (
              <pre className="text-[12px] whitespace-pre-wrap font-mono rounded-xl px-4 py-3 bg-muted text-muted-foreground">
                {JSON.stringify(value, null, 2)}
              </pre>
            ) : (
              <p className="text-[13px] text-muted-foreground">{String(value)}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ReadingProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const docHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      if (docHeight > 0) {
        setProgress(Math.min(100, (scrollTop / docHeight) * 100));
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div
      className="fixed top-0 left-0 z-50 h-[2px] transition-[width] duration-150 ease-out bg-gradient-to-r from-primary to-indigo-400"
      style={{ width: `${progress}%` }}
    />
  );
}

function TableOfContents({
  headings,
  activeId,
}: {
  headings: { id: string; text: string; level: number }[];
  activeId: string;
}) {
  if (headings.length < 2) return null;

  return (
    <nav className="space-y-0.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider mb-3 text-muted-foreground/70">
        On this page
      </p>
      {headings.map((h) => (
        <a
          key={h.id}
          href={`#${h.id}`}
          className={cn(
            "block text-[12px] py-1 transition-colors duration-150 hover:translate-x-0.5 border-l-2",
            activeId === h.id
              ? "text-primary border-primary font-medium"
              : "text-muted-foreground/70 border-transparent",
          )}
          style={{ paddingLeft: `${(h.level - 1) * 12}px` }}
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
        >
          {h.text}
        </a>
      ))}
    </nav>
  );
}

export default function PrepMaterialDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [material, setMaterial] = useState<PrepMaterial | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeHeading, setActiveHeading] = useState("");
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!params.id) return;
    fetch(`/api/ai/prep/materials/${params.id}`)
      .then((r) => r.json())
      .then((data) => {
        if (data?.material) setMaterial(data.material);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [params.id]);

  // Track active heading for ToC highlighting
  const headings = useMemo(
    () => (material ? extractHeadings(getMarkdownText(material) || "") : []),
    [material]
  );

  useEffect(() => {
    if (headings.length < 2) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveHeading(entry.target.id);
          }
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0.1 }
    );
    // Observe after a short delay so markdown has rendered
    const timer = setTimeout(() => {
      for (const h of headings) {
        const el = document.getElementById(h.id);
        if (el) observer.observe(el);
      }
    }, 500);
    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [headings]);

  const markdownText = material ? getMarkdownText(material) : null;
  const readTime = markdownText ? estimateReadTime(markdownText) : null;
  const hasToC = headings.length >= 2;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="text-center space-y-3">
          <svg className="h-6 w-6 animate-spin mx-auto text-primary" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-[11px] text-muted-foreground/70">Loading material...</p>
        </div>
      </div>
    );
  }

  if (!material) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <Button
          variant="ghost"
          onClick={() => router.push("/prep")}
          className="rounded-lg px-3 py-1.5 text-[12px] font-medium mb-6 flex items-center gap-1.5 text-primary"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Prep
        </Button>
        <Card className="p-12 text-center">
          <div className="relative z-10 space-y-3">
            <svg className="h-10 w-10 mx-auto text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            <p className="text-sm font-medium text-muted-foreground">Material not found</p>
            <p className="text-[11px] text-muted-foreground/70">It may have been deleted or the link is invalid.</p>
          </div>
        </Card>
      </div>
    );
  }

  const typeInfo = TYPE_BADGES[material.material_type] || TYPE_BADGES.general;
  const resources = Array.isArray(material.resources) ? material.resources : [];

  return (
    <>
      <ReadingProgress />

      <div className="max-w-6xl mx-auto px-6 pb-12">
        {/* Top bar */}
        <div className="pt-6 pb-4 flex items-center justify-between animate-fade-in">
          <Button
            variant="ghost"
            onClick={() => router.push("/prep")}
            className="rounded-lg px-3 py-1.5 text-[12px] font-medium flex items-center gap-1.5 text-primary"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Prep Materials
          </Button>
          <Button
            onClick={() => router.push(`/ai?source=prep&message=${encodeURIComponent(`Let's discuss my prep material: "${material.title}"`)}`)}
            className="rounded-lg px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            Discuss with AI
          </Button>
        </div>

        {/* Hero Header */}
        <Card
          className="px-8 py-8 mb-8 relative overflow-hidden animate-fade-in-up rounded-2xl"
        >
          {/* Decorative gradient orb */}
          <div
            className="absolute -top-20 -right-20 w-60 h-60 rounded-full blur-3xl opacity-10 pointer-events-none bg-primary"
          />
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <Badge variant={typeInfo.variant} className="inline-flex items-center gap-1.5 px-3 py-1">
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d={typeInfo.icon} />
                </svg>
                {typeInfo.label}
              </Badge>
              {material.company && (
                <Badge variant="info">
                  {material.company}
                </Badge>
              )}
              {material.role && (
                <Badge variant="secondary">
                  {material.role}
                </Badge>
              )}
              {material.scheduled_date && (
                <Badge variant="warning">
                  {new Date(material.scheduled_date).toLocaleDateString()}
                </Badge>
              )}
            </div>

            <h1 className="text-2xl font-bold leading-tight mb-3 text-foreground">
              {material.title}
            </h1>

            <div className="flex items-center gap-4 flex-wrap">
              {material.agent_source && (
                <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70">
                  <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                  </svg>
                  Generated by {material.agent_source}
                </span>
              )}
              <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70">
                <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                </svg>
                {new Date(material.created_at).toLocaleDateString(undefined, {
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}
              </span>
              {readTime && (
                <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70">
                  <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {readTime} min read
                </span>
              )}
            </div>
          </div>
        </Card>

        {/* Main layout: content + sidebar */}
        <div className={`flex gap-8 ${hasToC ? "" : "justify-center"}`}>
          {/* Article content */}
          <div
            ref={contentRef}
            className={cn("min-w-0 animate-fade-in-up [animation-delay:0.1s]", hasToC ? "flex-1 max-w-4xl" : "max-w-4xl w-full")}
          >
            <Card className="rounded-2xl px-8 py-8">
              <div className="relative z-10 article-prose">
                {renderContent(material)}
              </div>
            </Card>

            {/* Resources */}
            {resources.length > 0 && (
              <Card className="rounded-2xl px-8 py-6 mt-6 animate-fade-in-up [animation-delay:0.2s]">
                <div className="relative z-10">
                  <h2 className="text-[13px] font-semibold mb-4 flex items-center gap-2 text-foreground">
                    <svg className="h-4 w-4 text-primary" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-1.135a4.5 4.5 0 00-1.242-7.244l-4.5-4.5a4.5 4.5 0 00-6.364 6.364L4.757 8.25" />
                    </svg>
                    Resources ({resources.length})
                  </h2>
                  <div className="grid gap-2">
                    {resources.map((r, i) => (
                      <a
                        key={i}
                        href={r.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-200 group bg-muted hover:bg-accent hover:border-border"
                      >
                        <div className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0 bg-primary/10">
                          <svg className="h-4 w-4 text-primary" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                          </svg>
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[12px] font-medium truncate group-hover:underline text-primary">
                            {r.title || r.url}
                          </p>
                          {r.type && (
                            <p className="text-[10px] text-muted-foreground/70">{r.type}</p>
                          )}
                        </div>
                        <svg className="h-3.5 w-3.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                        </svg>
                      </a>
                    ))}
                  </div>
                </div>
              </Card>
            )}
          </div>

          {/* Sidebar: Table of Contents */}
          {hasToC && (
            <aside className="hidden lg:block w-56 shrink-0 animate-fade-in-up [animation-delay:0.2s]">
              <div className="sticky top-6">
                <Card className="rounded-2xl px-5 py-5">
                  <TableOfContents headings={headings} activeId={activeHeading} />
                </Card>

                {/* Quick stats */}
                <Card className="rounded-2xl px-5 py-4 mt-4">
                  <div className="space-y-3">
                    {readTime && (
                      <div className="flex items-center gap-2">
                        <svg className="h-3.5 w-3.5 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-[11px] text-muted-foreground/70">{readTime} min read</span>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <svg className="h-3.5 w-3.5 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" />
                      </svg>
                      <span className="text-[11px] text-muted-foreground/70">{headings.length} sections</span>
                    </div>
                  </div>
                </Card>
              </div>
            </aside>
          )}
        </div>
      </div>
    </>
  );
}
