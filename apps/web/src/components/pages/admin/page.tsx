"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

interface Stats {
  totalUsers: number;
  totalJobs: number;
  totalSearches: number;
  totalTokens: number;
  totalBotRuns: number;
}

interface SystemHealth {
  aiServiceStatus: "online" | "offline";
  dbSize: number;
  uptime: number;
}

interface User {
  id: string;
  email: string;
  name: string;
  imageUrl: string;
  createdAt: number;
  jobCount: number;
  searchCount: number;
  banned: boolean;
}

interface UserStats {
  totalJobs: number;
  totalSearches: number;
  jobsByStatus: { status: string; count: number }[];
  recentSearches: { search_term: string; location: string; searched_at: string }[];
  tokenUsage: { total_cost: number; total_input_tokens: number; total_output_tokens: number; total_runs: number } | null;
}

type Tab = "overview" | "users" | "system";

export default function AdminPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<Stats | null>(null);
  const [system, setSystem] = useState<SystemHealth | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [sortBy, setSortBy] = useState<"name" | "jobCount" | "searchCount" | "createdAt">("createdAt");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Auth check
  useEffect(() => {
    fetch("/api/admin/check")
      .then((r) => r.json())
      .then((d) => {
        if (!d.isAdmin) {
          router.replace("/");
        } else {
          setAuthorized(true);
        }
      })
      .catch(() => router.replace("/"));
  }, [router]);

  // Load stats + system on mount
  useEffect(() => {
    if (!authorized) return;
    fetch("/api/admin/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
    fetch("/api/admin/system")
      .then((r) => r.json())
      .then(setSystem)
      .catch(() => {});
  }, [authorized]);

  // Load users when tab switches
  useEffect(() => {
    if (tab !== "users" || !authorized) return;
    setLoadingUsers(true);
    fetch("/api/admin/users")
      .then((r) => r.json())
      .then((d) => {
        setUsers(d);
        setLoadingUsers(false);
      })
      .catch(() => setLoadingUsers(false));
  }, [tab, authorized]);

  // Load user detail
  useEffect(() => {
    if (!selectedUser) {
      setUserStats(null);
      return;
    }
    fetch(`/api/admin/users/${selectedUser}/stats`)
      .then((r) => r.json())
      .then(setUserStats)
      .catch(() => {});
  }, [selectedUser]);

  const toggleBan = async (userId: string, currentlyBanned: boolean) => {
    const method = currentlyBanned ? "DELETE" : "POST";
    const res = await fetch(`/api/admin/users/${userId}/disable`, { method });
    if (res.ok) {
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, banned: !currentlyBanned } : u))
      );
    }
  };

  const sortedUsers = [...users].sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    if (sortBy === "name") return a.name.localeCompare(b.name) * dir;
    if (sortBy === "jobCount") return (a.jobCount - b.jobCount) * dir;
    if (sortBy === "searchCount") return (a.searchCount - b.searchCount) * dir;
    return (a.createdAt - b.createdAt) * dir;
  });

  const handleSort = (col: typeof sortBy) => {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  const formatNumber = (n: number) => {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toString();
  };

  if (authorized === null) {
    return (
      <div className="flex h-full items-center justify-center">
        <Skeleton className="h-8 w-32" />
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "users", label: "Users" },
    { key: "system", label: "System" },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6 animate-page-enter">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-destructive/10">
            <svg className="h-4 w-4 text-destructive" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-foreground">
            Admin Dashboard
          </h1>
        </div>
        <p className="text-[13px] text-muted-foreground">
          User management, usage monitoring, and system health
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 rounded-xl bg-muted">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "px-4 py-2 rounded-lg text-[13px] font-medium transition-all duration-200",
              tab === t.key
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === "overview" && (
        <div className="stagger">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[
              { label: "Total Users", value: stats?.totalUsers ?? "—", colorClass: "text-primary" },
              { label: "Saved Jobs", value: stats ? formatNumber(stats.totalJobs) : "—", colorClass: "text-success" },
              { label: "Searches", value: stats ? formatNumber(stats.totalSearches) : "—", colorClass: "text-warning" },
              { label: "Bot Runs", value: stats ? formatNumber(stats.totalBotRuns) : "—", colorClass: "text-purple-500" },
            ].map((card) => (
              <Card key={card.label} className="p-5">
                <p className="text-[11px] font-semibold uppercase tracking-wide mb-2 text-muted-foreground">
                  {card.label}
                </p>
                <p className={cn("text-2xl font-bold data-mono", card.colorClass)}>
                  {card.value}
                </p>
              </Card>
            ))}
          </div>

          {stats && stats.totalTokens > 0 && (
            <Card className="p-5">
              <p className="text-[11px] font-semibold uppercase tracking-wide mb-2 text-muted-foreground">
                Total AI Tokens Used
              </p>
              <p className="text-2xl font-bold data-mono text-primary">
                {formatNumber(stats.totalTokens)}
              </p>
            </Card>
          )}
        </div>
      )}

      {/* Users Tab */}
      {tab === "users" && (
        <div>
          {loadingUsers ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : (
            <div className="flex gap-6">
              {/* User Table */}
              <div className="flex-1 min-w-0">
                <Card className="overflow-hidden">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b">
                        {[
                          { key: "name" as const, label: "User" },
                          { key: "jobCount" as const, label: "Jobs" },
                          { key: "searchCount" as const, label: "Searches" },
                          { key: "createdAt" as const, label: "Joined" },
                        ].map((col) => (
                          <th
                            key={col.key}
                            className="text-left px-4 py-3 font-semibold cursor-pointer select-none text-muted-foreground"
                            onClick={() => handleSort(col.key)}
                          >
                            <span className="flex items-center gap-1">
                              {col.label}
                              {sortBy === col.key && (
                                <span className="text-[10px]">{sortDir === "asc" ? "↑" : "↓"}</span>
                              )}
                            </span>
                          </th>
                        ))}
                        <th className="text-left px-4 py-3 font-semibold text-muted-foreground">
                          Status
                        </th>
                        <th className="px-4 py-3" />
                      </tr>
                    </thead>
                    <tbody>
                      {sortedUsers.map((user) => (
                        <tr
                          key={user.id}
                          className={cn(
                            "transition-colors duration-150 cursor-pointer border-b hover:bg-muted/50",
                            selectedUser === user.id && "bg-muted"
                          )}
                          onClick={() => setSelectedUser(selectedUser === user.id ? null : user.id)}
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <img
                                src={user.imageUrl}
                                alt=""
                                className="h-7 w-7 rounded-full border"
                              />
                              <div>
                                <p className="font-medium text-foreground">
                                  {user.name}
                                </p>
                                <p className="text-[11px] text-muted-foreground">
                                  {user.email}
                                </p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3 data-mono text-muted-foreground">
                            {user.jobCount}
                          </td>
                          <td className="px-4 py-3 data-mono text-muted-foreground">
                            {user.searchCount}
                          </td>
                          <td className="px-4 py-3 text-[12px] text-muted-foreground">
                            {new Date(user.createdAt).toLocaleDateString()}
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant={user.banned ? "destructive" : "success"}>
                              {user.banned ? "Banned" : "Active"}
                            </Badge>
                          </td>
                          <td className="px-4 py-3">
                            <Button
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleBan(user.id, user.banned);
                              }}
                              variant="outline"
                              size="sm"
                              className={cn(
                                "text-[11px]",
                                user.banned
                                  ? "text-success border-success/30 bg-success/10"
                                  : "text-destructive border-destructive/30 bg-destructive/10"
                              )}
                            >
                              {user.banned ? "Unban" : "Ban"}
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {sortedUsers.length === 0 && (
                    <div className="py-12 text-center text-[13px] text-muted-foreground">
                      No users found
                    </div>
                  )}
                </Card>
              </div>

              {/* User Detail Sidebar */}
              {selectedUser && userStats && (
                <div className="w-72 shrink-0 animate-slide-in-right">
                  <Card className="p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-[13px] font-semibold text-foreground">
                        User Detail
                      </h3>
                      <button
                        onClick={() => setSelectedUser(null)}
                        className="text-[11px] text-muted-foreground hover:text-foreground"
                      >
                        Close
                      </button>
                    </div>

                    <div className="space-y-3">
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                          Jobs by Status
                        </p>
                        <div className="mt-2 space-y-1">
                          {userStats.jobsByStatus.map((s) => (
                            <div key={s.status} className="flex items-center justify-between text-[12px]">
                              <span className="capitalize text-muted-foreground">{s.status}</span>
                              <span className="data-mono font-medium text-foreground">{s.count}</span>
                            </div>
                          ))}
                          {userStats.jobsByStatus.length === 0 && (
                            <p className="text-[11px] text-muted-foreground">No jobs saved</p>
                          )}
                        </div>
                      </div>

                      <Separator />

                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                          Recent Searches
                        </p>
                        <div className="mt-2 space-y-1.5">
                          {userStats.recentSearches.map((s, i) => (
                            <div key={i} className="text-[12px]">
                              <span className="text-foreground">{s.search_term}</span>
                              {s.location && (
                                <span className="text-muted-foreground"> in {s.location}</span>
                              )}
                            </div>
                          ))}
                          {userStats.recentSearches.length === 0 && (
                            <p className="text-[11px] text-muted-foreground">No searches</p>
                          )}
                        </div>
                      </div>

                      {userStats.tokenUsage && (
                        <>
                          <Separator />
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                              AI Usage
                            </p>
                            <div className="mt-2 space-y-1">
                              <div className="flex justify-between text-[12px]">
                                <span className="text-muted-foreground">Total Runs</span>
                                <span className="data-mono text-foreground">
                                  {userStats.tokenUsage.total_runs}
                                </span>
                              </div>
                              <div className="flex justify-between text-[12px]">
                                <span className="text-muted-foreground">Tokens</span>
                                <span className="data-mono text-foreground">
                                  {formatNumber(userStats.tokenUsage.total_input_tokens + userStats.tokenUsage.total_output_tokens)}
                                </span>
                              </div>
                              <div className="flex justify-between text-[12px]">
                                <span className="text-muted-foreground">Cost</span>
                                <span className="data-mono text-foreground">
                                  ${userStats.tokenUsage.total_cost.toFixed(4)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </Card>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* System Tab */}
      {tab === "system" && (
        <div className="stagger grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-5">
            <p className="text-[11px] font-semibold uppercase tracking-wide mb-3 text-muted-foreground">
              AI Service
            </p>
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  system?.aiServiceStatus === "online" ? "bg-success" : "bg-destructive"
                )}
                style={{
                  boxShadow: system?.aiServiceStatus === "online"
                    ? "0 0 8px rgba(86, 211, 100, 0.4)"
                    : "0 0 8px rgba(248, 81, 73, 0.4)",
                }}
              />
              <span className={cn(
                "text-[14px] font-semibold capitalize",
                system?.aiServiceStatus === "online" ? "text-success" : "text-destructive"
              )}>
                {system?.aiServiceStatus ?? "Checking..."}
              </span>
            </div>
          </Card>

          <Card className="p-5">
            <p className="text-[11px] font-semibold uppercase tracking-wide mb-3 text-muted-foreground">
              Database Size
            </p>
            <p className="text-xl font-bold data-mono text-primary">
              {system ? formatBytes(system.dbSize) : "—"}
            </p>
          </Card>

          <Card className="p-5">
            <p className="text-[11px] font-semibold uppercase tracking-wide mb-3 text-muted-foreground">
              Process Uptime
            </p>
            <p className="text-xl font-bold data-mono text-primary">
              {system ? formatUptime(system.uptime) : "—"}
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}
