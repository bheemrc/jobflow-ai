"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

// Lightweight syntax highlighting -- regex-based token coloring for common languages
const TOKEN_COLORS = {
  keyword: "#FF7B72",
  string: "#A5D6FF",
  comment: "#8B949E",
  number: "#79C0FF",
  function: "#D2A8FF",
  type: "#FFA657",
  operator: "#FF7B72",
  punctuation: "#C9D1D9",
  builtin: "#79C0FF",
};

type TokenRule = { pattern: RegExp; token: keyof typeof TOKEN_COLORS };
const LANG_RULES: Record<string, TokenRule[] | string> = {
  _common: [
    { pattern: /(\/\/.*$|#.*$)/gm, token: "comment" },
    { pattern: /(\/\*[\s\S]*?\*\/)/g, token: "comment" },
    { pattern: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)/g, token: "string" },
    { pattern: /\b(\d+\.?\d*(?:e[+-]?\d+)?)\b/gi, token: "number" },
  ],
  js: [
    { pattern: /\b(const|let|var|function|return|if|else|for|while|class|import|export|from|default|async|await|new|this|typeof|instanceof|try|catch|throw|switch|case|break|continue|yield|of|in)\b/g, token: "keyword" },
    { pattern: /\b(true|false|null|undefined|NaN|Infinity)\b/g, token: "builtin" },
    { pattern: /\b(console|window|document|Array|Object|Promise|Map|Set|Math|JSON|RegExp|Error|Date|String|Number|Boolean)\b/g, token: "type" },
    { pattern: /\b([a-zA-Z_$][\w$]*)\s*(?=\()/g, token: "function" },
    { pattern: /(=>|===|!==|==|!=|<=|>=|&&|\|\||[+\-*/%]=?)/g, token: "operator" },
  ],
  py: [
    { pattern: /\b(def|class|return|if|elif|else|for|while|import|from|as|with|try|except|raise|finally|yield|lambda|pass|break|continue|and|or|not|in|is|global|nonlocal|async|await)\b/g, token: "keyword" },
    { pattern: /\b(True|False|None)\b/g, token: "builtin" },
    { pattern: /\b(int|str|float|list|dict|tuple|set|bool|type|print|len|range|enumerate|zip|map|filter|super|self|cls)\b/g, token: "type" },
    { pattern: /\b([a-zA-Z_]\w*)\s*(?=\()/g, token: "function" },
  ],
  ts: "js",
  tsx: "js",
  jsx: "js",
  typescript: "js",
  javascript: "js",
  python: "py",
  rust: [
    { pattern: /\b(fn|let|mut|const|if|else|for|while|loop|match|return|struct|enum|impl|trait|pub|use|mod|crate|self|super|where|async|await|move|ref|type|unsafe|extern|dyn)\b/g, token: "keyword" },
    { pattern: /\b(true|false|Some|None|Ok|Err|Self)\b/g, token: "builtin" },
    { pattern: /\b(i8|i16|i32|i64|u8|u16|u32|u64|f32|f64|bool|char|str|String|Vec|Option|Result|Box|Rc|Arc|HashMap|HashSet)\b/g, token: "type" },
    { pattern: /\b([a-zA-Z_]\w*)\s*(?=\()/g, token: "function" },
  ],
  go: [
    { pattern: /\b(func|var|const|type|struct|interface|map|chan|range|return|if|else|for|switch|case|default|break|continue|go|defer|select|package|import|fallthrough)\b/g, token: "keyword" },
    { pattern: /\b(true|false|nil|iota)\b/g, token: "builtin" },
    { pattern: /\b(int|int8|int16|int32|int64|uint|float32|float64|string|bool|byte|rune|error|any)\b/g, token: "type" },
    { pattern: /\b([a-zA-Z_]\w*)\s*(?=\()/g, token: "function" },
  ],
  sql: [
    { pattern: /\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|BETWEEN|LIKE|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|AS|INTO|VALUES|SET|NULL|IS|EXISTS|UNION|ALL|DISTINCT|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END)\b/gi, token: "keyword" },
    { pattern: /\b(INT|VARCHAR|TEXT|BOOLEAN|DATE|TIMESTAMP|FLOAT|DECIMAL|SERIAL|PRIMARY|KEY|FOREIGN|REFERENCES|UNIQUE|DEFAULT|NOT|AUTO_INCREMENT)\b/gi, token: "type" },
  ],
  bash: [
    { pattern: /\b(if|then|else|elif|fi|for|while|do|done|case|esac|function|return|exit|export|source|alias|local|readonly|shift|eval|exec|trap)\b/g, token: "keyword" },
    { pattern: /(\$\{?[a-zA-Z_]\w*\}?)/g, token: "builtin" },
  ],
  sh: "bash",
  shell: "bash",
  json: [
    { pattern: /("(?:[^"\\]|\\.)*")\s*:/g, token: "type" },
    { pattern: /:\s*("(?:[^"\\]|\\.)*")/g, token: "string" },
    { pattern: /\b(true|false|null)\b/g, token: "builtin" },
    { pattern: /\b(\d+\.?\d*)\b/g, token: "number" },
  ],
  css: [
    { pattern: /([.#][\w-]+)/g, token: "type" },
    { pattern: /\b(px|em|rem|vh|vw|%|deg|ms|s)\b/g, token: "number" },
    { pattern: /(--[\w-]+)/g, token: "builtin" },
    { pattern: /\b(color|background|border|margin|padding|display|flex|grid|position|font|width|height|top|left|right|bottom|opacity|transform|transition|animation|z-index|overflow)\b/g, token: "keyword" },
  ],
  html: [
    { pattern: /(<\/?[a-zA-Z][\w-]*)/g, token: "keyword" },
    { pattern: /\b([a-zA-Z-]+)(?==)/g, token: "type" },
    { pattern: /(<!--[\s\S]*?-->)/g, token: "comment" },
  ],
  yaml: [
    { pattern: /^(\s*[\w.-]+)(?=:)/gm, token: "type" },
    { pattern: /\b(true|false|null|yes|no)\b/gi, token: "builtin" },
  ],
  yml: "yaml",
};

// Resolve language alias
function resolveRules(lang: string): TokenRule[] {
  let rules = LANG_RULES[lang];
  if (typeof rules === "string") rules = LANG_RULES[rules];
  if (!rules || typeof rules === "string") return (LANG_RULES._common as TokenRule[]) || [];
  return [...((LANG_RULES._common as TokenRule[]) || []), ...rules];
}

function highlightCode(code: string, lang: string): string {
  const rules = resolveRules(lang);
  if (rules.length === 0) return escapeHtml(code);

  // Tokenize: find all matches, sort by position, apply non-overlapping
  type Match = { start: number; end: number; token: keyof typeof TOKEN_COLORS };
  const matches: Match[] = [];

  for (const rule of rules) {
    // Must copy: g-flag regexes are stateful (lastIndex). Sharing module-level
    // patterns across concurrent React renders would corrupt iteration state.
    const re = new RegExp(rule.pattern.source, rule.pattern.flags);
    let m: RegExpExecArray | null;
    while ((m = re.exec(code)) !== null) {
      // Use the last capture group if exists, otherwise full match
      const group = m[m.length > 1 ? 1 : 0];
      const start = m.index + (m.length > 1 ? m[0].indexOf(group) : 0);
      matches.push({ start, end: start + group.length, token: rule.token });
    }
  }

  // Sort by start position, longer matches first for ties
  matches.sort((a, b) => a.start - b.start || b.end - a.end);

  // Remove overlapping matches (keep earlier/longer)
  const filtered: Match[] = [];
  let lastEnd = 0;
  for (const m of matches) {
    if (m.start >= lastEnd) {
      filtered.push(m);
      lastEnd = m.end;
    }
  }

  // Build highlighted HTML
  let result = "";
  let pos = 0;
  for (const m of filtered) {
    if (m.start > pos) result += escapeHtml(code.slice(pos, m.start));
    result += `<span style="color:${TOKEN_COLORS[m.token]}">${escapeHtml(code.slice(m.start, m.end))}</span>`;
    pos = m.end;
  }
  if (pos < code.length) result += escapeHtml(code.slice(pos));
  return result;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const LANG_LABELS: Record<string, string> = {
  js: "JavaScript", javascript: "JavaScript", ts: "TypeScript", typescript: "TypeScript",
  jsx: "JSX", tsx: "TSX", py: "Python", python: "Python", rust: "Rust", go: "Go",
  sql: "SQL", bash: "Bash", sh: "Shell", shell: "Shell", json: "JSON", css: "CSS",
  html: "HTML", yaml: "YAML", yml: "YAML", md: "Markdown", toml: "TOML", xml: "XML",
  c: "C", cpp: "C++", java: "Java", rb: "Ruby", ruby: "Ruby", swift: "Swift",
  kotlin: "Kotlin", dart: "Dart", r: "R", php: "PHP", lua: "Lua", zig: "Zig",
};

function MermaidBlock({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import("mermaid").then((mod) => {
      const mermaid = mod.default;
      mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        themeVariables: {
          darkMode: true,
          background: "transparent",
          primaryColor: "#38BDF8",
          primaryTextColor: "#E2E8F0",
          lineColor: "#64748B",
          secondaryColor: "#818CF8",
        },
      });
      const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
      mermaid.render(id, chart).then(({ svg: renderedSvg }) => {
        if (!cancelled) setSvg(renderedSvg);
      }).catch(() => {
        if (!cancelled) setError(true);
      });
    }).catch(() => {
      if (!cancelled) setError(true);
    });
    return () => { cancelled = true; };
  }, [chart]);

  if (error) {
    return (
      <pre className="rounded-xl px-3 py-2 my-2 overflow-x-auto text-[12px] data-mono bg-background border text-foreground">
        <code>{chart}</code>
      </pre>
    );
  }

  if (!svg) {
    return (
      <div className="rounded-xl px-3 py-4 my-2 flex items-center justify-center bg-background border">
        <span className="text-[11px] text-muted-foreground/70">Rendering diagram...</span>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="rounded-xl px-3 py-2 my-2 overflow-x-auto bg-background border"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <button
      onClick={handleCopy}
      className={cn(
        "absolute top-2 right-2 rounded-md px-2 py-1 text-[10px] font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-150 bg-accent border",
        copied ? "text-success" : "text-muted-foreground",
      )}
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

/** Recursively extract text content from React children. */
function extractTextContent(children: React.ReactNode): string {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (!children) return "";
  if (Array.isArray(children)) return children.map(extractTextContent).join("");
  if (typeof children === "object" && children !== null && "props" in (children as unknown as Record<string, unknown>)) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return extractTextContent((children as any).props.children);
  }
  return "";
}

/** Strip the [!TYPE] marker from text, returning { type, rest }. */
function stripCalloutMarker(text: string): { type: string | null; rest: string } {
  const match = text.match(/^\[!(TLDR|TIP|NOTE|WARNING|INSIGHT)\]\s*/i);
  if (match) {
    return { type: match[1].toUpperCase(), rest: text.slice(match[0].length) };
  }
  return { type: null, rest: text };
}

const CALLOUT_CONFIG: Record<string, { className: string; icon: string; label: string; colorClass: string }> = {
  TLDR: { className: "callout-tldr", icon: "\u26A1", label: "TL;DR", colorClass: "text-primary" },
  TIP: { className: "callout-tip", icon: "\uD83D\uDCA1", label: "Tip", colorClass: "text-success" },
  NOTE: { className: "callout-note", icon: "\u2139\uFE0F", label: "Note", colorClass: "text-primary" },
  WARNING: { className: "callout-warning", icon: "\u26A0\uFE0F", label: "Warning", colorClass: "text-warning" },
  INSIGHT: { className: "callout-insight", icon: "\u2728", label: "Insight", colorClass: "text-purple-400" },
};

const markdownComponents = {
  a: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="md-link"
      {...props}
    >
      {children}
    </a>
  ),
  ul: ({ children, ...props }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="pl-4 my-1.5 space-y-1" style={{ listStyleType: "'\u25C7 '" }} {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="list-decimal pl-4 my-1.5 space-y-1 marker:text-primary marker:font-semibold" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }: React.HTMLAttributes<HTMLLIElement>) => (
    <li className="leading-relaxed pl-0.5 text-muted-foreground" {...props}>{children}</li>
  ),
  p: ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="my-1.5 leading-relaxed" {...props}>{children}</p>
  ),
  strong: ({ children, ...props }: React.HTMLAttributes<HTMLElement>) => (
    <strong className="font-semibold text-foreground" {...props}>{children}</strong>
  ),
  h1: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => {
    const text = typeof children === "string" ? children : String(children);
    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    return <h1 id={id} className="text-base font-bold mt-3 mb-1 scroll-mt-20 text-foreground" {...props}>{children}</h1>;
  },
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => {
    const text = typeof children === "string" ? children : String(children);
    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    return <h2 id={id} className="text-sm font-bold mt-2.5 mb-1 scroll-mt-20 text-foreground" {...props}>{children}</h2>;
  },
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => {
    const text = typeof children === "string" ? children : String(children);
    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    return <h3 id={id} className="text-sm font-semibold mt-2 mb-0.5 scroll-mt-20 text-foreground" {...props}>{children}</h3>;
  },
  code: ({ children, className, ...props }: React.HTMLAttributes<HTMLElement>) => {
    const isBlock = className?.includes("language-");
    const isMermaid = className?.includes("language-mermaid");
    const lang = className?.replace("language-", "") || "";

    if (isMermaid) {
      const chart = String(children).replace(/\n$/, "");
      return <MermaidBlock chart={chart} />;
    }

    if (isBlock) {
      const codeText = String(children).replace(/\n$/, "");
      const highlighted = highlightCode(codeText, lang);
      const langLabel = LANG_LABELS[lang] || (lang ? lang.toUpperCase() : null);
      return (
        <div className="relative group my-2">
          {langLabel && (
            <div className="flex items-center justify-between px-3 py-1.5 rounded-t-xl text-[10px] font-semibold data-mono bg-muted/50 border border-b-0 text-muted-foreground/70">
              <span>{langLabel}</span>
            </div>
          )}
          <pre
            className={cn(
              "px-3 py-2.5 overflow-x-auto text-[12px] leading-[1.7] data-mono bg-background border text-foreground",
              langLabel ? "rounded-b-xl" : "rounded-xl",
              langLabel && "border-t-0",
            )}
          >
            <code
              {...props}
              dangerouslySetInnerHTML={{ __html: highlighted }}
            />
          </pre>
          <CopyButton text={codeText} />
        </div>
      );
    }
    return (
      <code
        className="rounded px-1.5 py-0.5 text-[12px] data-mono bg-primary/8 text-primary border border-primary/10"
        {...props}
      >
        {children}
      </code>
    );
  },
  hr: (props: React.HTMLAttributes<HTMLHRElement>) => (
    <Separator className="my-2" {...props} />
  ),
  blockquote: ({ children, ...props }: React.HTMLAttributes<HTMLQuoteElement>) => {
    // Extract full text to detect [!TYPE] callout markers
    const fullText = extractTextContent(children);
    const { type } = stripCalloutMarker(fullText.trimStart());

    if (type && CALLOUT_CONFIG[type]) {
      const config = CALLOUT_CONFIG[type];

      // Strip the [!TYPE] marker from the rendered children
      const processChildren = (kids: React.ReactNode): React.ReactNode => {
        if (!kids) return kids;
        if (Array.isArray(kids)) {
          let stripped = false;
          return kids.map((child, i) => {
            if (stripped) return child;
            const processed = processChildren(child);
            if (processed !== child) stripped = true;
            return processed;
          });
        }
        if (typeof kids === "object" && kids !== null && "props" in (kids as unknown as Record<string, unknown>)) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const el = kids as any;
          const childText = extractTextContent(el.props.children);
          const { type: innerType, rest } = stripCalloutMarker(childText.trimStart());
          if (innerType) {
            // Re-render the child element with the marker stripped
            return React.cloneElement(el, {}, rest || null);
          }
          // Recurse into nested children
          const processed = processChildren(el.props.children);
          if (processed !== el.props.children) {
            return React.cloneElement(el, {}, processed);
          }
        }
        return kids;
      };

      const strippedChildren = processChildren(children);

      return (
        <div className={`callout ${config.className}`}>
          <div className={cn("callout-header", config.colorClass)}>
            <span>{config.icon}</span>
            <span>{config.label}</span>
          </div>
          <div className="text-muted-foreground">
            {strippedChildren}
          </div>
        </div>
      );
    }

    return (
      <blockquote
        className="pl-3 my-1.5 italic border-l-2 border-primary text-muted-foreground"
        {...props}
      >
        {children}
      </blockquote>
    );
  },
  table: ({ children, ...props }: React.HTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto my-2 rounded-xl border">
      <table
        className="min-w-full text-[12px]"
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead className="bg-muted" {...props}>{children}</thead>
  ),
  tbody: ({ children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <tbody className="md-table-striped" {...props}>{children}</tbody>
  ),
  tr: ({ children, ...props }: React.HTMLAttributes<HTMLTableRowElement>) => (
    <tr
      className="md-tr"
      {...props}
    >
      {children}
    </tr>
  ),
  th: ({ children, ...props }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <th
      className="px-3 py-1.5 text-left font-semibold text-[11px] uppercase tracking-wider border-b text-muted-foreground/70"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <td
      className="px-3 py-1.5 text-muted-foreground"
      {...props}
    >
      {children}
    </td>
  ),
};

const Markdown = React.memo(function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents as any}>
      {children}
    </ReactMarkdown>
  );
});

export default Markdown;
