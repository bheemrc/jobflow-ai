"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  LayoutGrid,
  Search,
  Briefcase,
  GraduationCap,
  Sparkles,
  Cpu,
  Newspaper,
  MessagesSquare,
  Zap,
  FlaskConical,
  Swords,
  Inbox,
  Settings,
  ShieldCheck,
  ChevronDown,
  User,
} from "lucide-react";

export default function Nav() {
  const pathname = usePathname();
  const [jobCount, setJobCount] = useState(0);
  const [approvalCount, setApprovalCount] = useState(0);
  const [isAdminUser, setIsAdminUser] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const roomCount = useAppStore((s) => s.rooms.length);
  const runningBotCount = useAppStore((s) => s.botStates.filter((b) => b.status === "running").length);

  useEffect(() => {
    const stored = localStorage.getItem("nav-advanced");
    if (stored === "true") setShowAdvanced(true);
  }, []);

  useEffect(() => {
    fetch("/api/jobs")
      .then((r) => r.json())
      .then((jobs) => {
        if (Array.isArray(jobs)) setJobCount(jobs.length);
      })
      .catch(() => {});

    fetch("/api/ai/approvals")
      .then((r) => r.json())
      .then((data) => {
        if (data?.approvals) setApprovalCount(data.approvals.length);
      })
      .catch(() => {});

    fetch("/api/admin/check")
      .then((r) => r.json())
      .then((d) => { if (d?.isAdmin) setIsAdminUser(true); })
      .catch(() => {});
  }, [pathname]);

  function toggleAdvanced() {
    setShowAdvanced((prev) => {
      const next = !prev;
      localStorage.setItem("nav-advanced", String(next));
      return next;
    });
  }

  const primaryLinks = [
    { href: "/", label: "Dashboard", icon: LayoutGrid },
    { href: "/search", label: "Find Jobs", icon: Search },
    { href: "/saved", label: "My Pipeline", badge: jobCount || undefined, icon: Briefcase },
    { href: "/prep", label: "Prepare", icon: GraduationCap },
    { href: "/ai", label: "AI Coach", badge: roomCount || undefined, icon: Sparkles },
  ];

  const advancedLinks = [
    { href: "/bots", label: "Agents", badge: runningBotCount || undefined, icon: Cpu },
    { href: "/timeline", label: "Signals", icon: Newspaper },
    { href: "/group-chats", label: "Councils", icon: MessagesSquare },
    { href: "/katalyst", label: "Katalyst", icon: Zap },
    { href: "/research", label: "Research", icon: FlaskConical },
    { href: "/arena", label: "Arena", icon: Swords },
    { href: "/inbox", label: "Inbox", badge: approvalCount || undefined, icon: Inbox },
  ];

  const renderLink = (link: { href: string; label: string; badge?: number; icon: React.ComponentType<{ className?: string }> }, isExact = false) => {
    const isActive = isExact ? pathname === link.href : pathname.startsWith(link.href);
    const Icon = link.icon;
    return (
      <Link
        key={link.href}
        href={link.href}
        className={cn(
          "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors",
          isActive
            ? "bg-primary/10 text-primary"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        )}
      >
        {isActive && (
          <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
        )}
        <Icon className={cn("h-[18px] w-[18px]", isActive ? "text-primary" : "text-muted-foreground/70")} />
        {link.label}
        {link.badge ? (
          <Badge variant="default" className="ml-auto h-[18px] min-w-[18px] px-1.5 text-[9px]">
            {link.badge}
          </Badge>
        ) : null}
      </Link>
    );
  };

  return (
    <nav className="flex h-screen w-[220px] shrink-0 flex-col border-r bg-sidebar">
      {/* Logo */}
      <div className="flex h-14 items-center px-4">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm transition-all duration-300 group-hover:scale-105">
            <span className="text-sm font-bold">JF</span>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-[15px] font-bold tracking-tight text-foreground">
              JobFlow
            </span>
            <span className="data-mono text-[8px] font-bold tracking-[0.2em] uppercase text-muted-foreground">
              AI
            </span>
          </div>
        </Link>
      </div>

      <Separator className="mx-4" />

      {/* Main nav links */}
      <div className="flex flex-1 flex-col gap-0.5 px-3 py-2 overflow-y-auto">
        <p className="px-3 mb-1 text-[10px] font-bold tracking-[0.08em] uppercase text-muted-foreground">Main</p>
        {primaryLinks.map((link) => renderLink(link, link.href === "/"))}

        {/* Advanced section */}
        <div className="mt-3">
          <button
            onClick={toggleAdvanced}
            className={cn(
              "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-colors",
              showAdvanced ? "bg-primary/5 text-muted-foreground" : "text-muted-foreground hover:bg-accent"
            )}
          >
            <Settings className="h-3.5 w-3.5" />
            <span>Advanced</span>
            <ChevronDown
              className={cn(
                "h-3 w-3 ml-auto transition-transform duration-200",
                showAdvanced && "rotate-180"
              )}
            />
          </button>

          {showAdvanced && (
            <div className="mt-1 space-y-0.5 animate-fade-in">
              {advancedLinks.map((link) => renderLink(link))}
            </div>
          )}
        </div>
      </div>

      {/* Admin link */}
      {isAdminUser && (
        <div className="px-3 mb-1">
          {renderLink({
            href: "/admin",
            label: "Admin",
            icon: ShieldCheck,
          })}
        </div>
      )}

      {/* Footer — user avatar */}
      <div className="px-4 py-3 border-t">
        <a href="/sign-in" className="flex items-center gap-3">
          <div className="h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-semibold bg-muted text-foreground border">
            <User className="h-3.5 w-3.5" />
          </div>
          <span className="text-[12px] font-medium text-muted-foreground">
            Sign in
          </span>
        </a>
      </div>
    </nav>
  );
}
