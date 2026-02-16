"use client";

import { cn } from "@/lib/utils";

// Agent avatar configuration - matches nav.tsx collective with extended info
const AGENT_CONFIG: Record<string, {
  avatar: string;
  color: string;
  name: string;
  role?: string;
  description?: string;
}> = {
  pathfinder: {
    avatar: "\u26A1",
    color: "#F97316",
    name: "Pathfinder",
    role: "Explorer",
    description: "Finds alternative paths and creative solutions",
  },
  forge: {
    avatar: "\uD83D\uDD25",
    color: "#EF4444",
    name: "Forge",
    role: "Builder",
    description: "Builds skills and career development plans",
  },
  strategist: {
    avatar: "\u265F\uFE0F",
    color: "#A78BFA",
    name: "Strategist",
    role: "Planner",
    description: "Creates actionable business strategies",
  },
  cipher: {
    avatar: "\u25C8",
    color: "#22D3EE",
    name: "Cipher",
    role: "Analyst",
    description: "Digs deep into research and data",
  },
  architect: {
    avatar: "\u25B3",
    color: "#818CF8",
    name: "Architect",
    role: "Designer",
    description: "Designs systems and technical solutions",
  },
  oracle: {
    avatar: "\u25C9",
    color: "#4ADE80",
    name: "Oracle",
    role: "Visionary",
    description: "Spots patterns and predicts trends",
  },
  sentinel: {
    avatar: "\u25C6",
    color: "#94A3B8",
    name: "Sentinel",
    role: "Guardian",
    description: "Identifies risks and ensures safety",
  },
  catalyst: {
    avatar: "\u2726",
    color: "#FBBF24",
    name: "Catalyst",
    role: "Connector",
    description: "Creates connections and opportunities",
  },
  compass: {
    avatar: "\u2295",
    color: "#F472B6",
    name: "Compass",
    role: "Guide",
    description: "Provides guidance and mentorship",
  },
  nexus: {
    avatar: "\u2B21",
    color: "#58A6FF",
    name: "Nexus",
    role: "Integrator",
    description: "Synthesizes ideas and coordinates efforts",
  },
  researcher: {
    avatar: "\uD83D\uDD2C",
    color: "#10B981",
    name: "Researcher",
    role: "Scholar",
    description: "Deep-dives into scientific literature",
  },
  tech_analyst: {
    avatar: "\uD83D\uDCCA",
    color: "#6366F1",
    name: "Tech Analyst",
    role: "Evaluator",
    description: "Tracks technology readiness and patents",
  },
  market_intel: {
    avatar: "\uD83D\uDCC8",
    color: "#EC4899",
    name: "Market Intel",
    role: "Scout",
    description: "Monitors market trends and signals",
  },
  contrarian: {
    avatar: "\u2694\uFE0F",
    color: "#F43F5E",
    name: "Contrarian",
    role: "Challenger",
    description: "Challenges assumptions and finds weaknesses",
  },
  synthesizer: {
    avatar: "\uD83E\uDDEC",
    color: "#8B5CF6",
    name: "Synthesizer",
    role: "Unifier",
    description: "Connects ideas across domains",
  },
};

type AvatarSize = "xs" | "sm" | "md" | "lg";

interface AgentAvatarProps {
  agent: string;
  size?: AvatarSize;
  showPulse?: boolean;
  className?: string;
}

export function AgentAvatar({ agent, size = "md", showPulse = false, className = "" }: AgentAvatarProps) {
  const config = AGENT_CONFIG[agent.toLowerCase()] || {
    avatar: agent.charAt(0).toUpperCase(),
    color: "#58A6FF",
    name: agent,
  };

  const sizeClasses: Record<AvatarSize, string> = {
    xs: "h-4 w-4 text-[8px]",
    sm: "h-6 w-6 text-[10px]",
    md: "h-8 w-8 text-xs",
    lg: "h-10 w-10 text-sm",
  };

  return (
    <div className={cn("relative", className)}>
      <div
        className={cn(
          sizeClasses[size],
          "rounded-xl flex items-center justify-center font-medium transition-transform hover:scale-105"
        )}
        style={{
          background: `${config.color}20`,
          border: `1px solid ${config.color}40`,
          color: config.color,
        }}
        title={config.name}
      >
        {config.avatar}
      </div>
      {showPulse && (
        <span
          className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full animate-pulse"
          style={{
            background: config.color,
            boxShadow: `0 0 8px ${config.color}60`,
          }}
        />
      )}
    </div>
  );
}

// Generate a consistent color from a string (for dynamic agents)
function stringToColor(str: string): string {
  const colors = [
    "#F97316", "#EF4444", "#A78BFA", "#22D3EE", "#818CF8",
    "#4ADE80", "#FBBF24", "#F472B6", "#10B981", "#6366F1",
    "#EC4899", "#F43F5E", "#8B5CF6", "#06B6D4", "#84CC16",
  ];
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

// Parse dynamic agent name to extract info
// e.g., "nasaadvisor" -> { avatar: "NA", name: "NASA Advisor", role: "Advisor" }
function parseDynamicAgentName(name: string): { avatar: string; name: string; role: string } {
  // Common role suffixes to detect
  const roleSuffixes = [
    "advisor", "professor", "engineer", "architect", "analyst",
    "specialist", "consultant", "expert", "researcher", "leader",
    "executive", "manager", "critic", "officer", "technician",
  ];

  const lower = name.toLowerCase();
  let role = "Specialist";
  let prefix = name;

  // Find role suffix
  for (const suffix of roleSuffixes) {
    if (lower.endsWith(suffix)) {
      role = suffix.charAt(0).toUpperCase() + suffix.slice(1);
      prefix = name.slice(0, -suffix.length);
      break;
    }
  }

  // Format display name (add spaces before capitals)
  const displayName = name
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2");

  // Generate avatar from initials
  const words = displayName.split(/\s+/);
  const avatar = words.length >= 2
    ? words[0].charAt(0) + words[1].charAt(0)
    : displayName.slice(0, 2).toUpperCase();

  return { avatar, name: displayName, role };
}

export function getAgentConfig(agent: string) {
  const staticConfig = AGENT_CONFIG[agent.toLowerCase()];
  if (staticConfig) {
    return staticConfig;
  }

  // Handle dynamic agent
  const parsed = parseDynamicAgentName(agent);
  return {
    avatar: parsed.avatar,
    color: stringToColor(agent),
    name: parsed.name,
    role: parsed.role,
    description: `Dynamic agent: ${parsed.role}`,
  };
}
