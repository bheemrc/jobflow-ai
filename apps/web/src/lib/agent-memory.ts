"use client";

import type { TimelinePost } from "./use-timeline-events";

// ═══════════════════════════════════════════════════════════════════
// AGENT MEMORY — lightweight client-side memory for agent context
// Tracks topics, interaction frequency, and expertise signals
// ═══════════════════════════════════════════════════════════════════

export interface AgentMemory {
  agentKey: string;
  totalPosts: number;
  totalVotes: number;
  topTopics: string[];         // top 5 topics by frequency
  recentInteractions: number;  // posts in last 24h
  firstSeen: string;           // ISO date
  lastSeen: string;            // ISO date
  realms: Record<string, number>; // realm → post count
  interactedWith: string[];    // agents they've replied to
  streak: number;              // consecutive days active
}

const STOP_WORDS = new Set([
  "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for",
  "not", "on", "with", "he", "as", "you", "do", "at", "this", "but", "his",
  "by", "from", "they", "we", "say", "her", "she", "or", "an", "will", "my",
  "one", "all", "would", "there", "their", "what", "so", "up", "out", "if",
  "about", "who", "get", "which", "go", "me", "when", "can", "like", "just",
  "him", "know", "take", "people", "into", "year", "your", "some", "them",
  "than", "then", "now", "look", "only", "come", "its", "also", "more", "after",
  "use", "how", "our", "way", "even", "new", "want", "any", "these", "give",
  "most", "us", "are", "is", "was", "were", "been", "has", "had", "could",
  "should", "does", "did", "being", "am", "here", "think", "make", "very",
  "much", "well", "really", "still", "over", "such", "good", "own", "too",
]);

function extractKeywords(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 3 && !STOP_WORDS.has(w));
}

/** Build memory profiles for all agents from post data */
export function buildAgentMemories(posts: TimelinePost[]): Map<string, AgentMemory> {
  const memories = new Map<string, AgentMemory>();
  const now = Date.now();
  const oneDayAgo = now - 86_400_000;

  // Track topic frequencies per agent
  const topicFreqs = new Map<string, Map<string, number>>();

  for (const post of posts) {
    if (post.agent === "user") continue;

    let mem = memories.get(post.agent);
    if (!mem) {
      mem = {
        agentKey: post.agent,
        totalPosts: 0,
        totalVotes: 0,
        topTopics: [],
        recentInteractions: 0,
        firstSeen: post.created_at,
        lastSeen: post.created_at,
        realms: {},
        interactedWith: [],
        streak: 0,
      };
      memories.set(post.agent, mem);
    }

    mem.totalPosts++;
    mem.totalVotes += post.votes || 0;

    // Track timing
    if (new Date(post.created_at) < new Date(mem.firstSeen)) {
      mem.firstSeen = post.created_at;
    }
    if (new Date(post.created_at) > new Date(mem.lastSeen)) {
      mem.lastSeen = post.created_at;
    }

    if (new Date(post.created_at).getTime() > oneDayAgo) {
      mem.recentInteractions++;
    }

    // Track realms
    const realm = post.realm || (post.context?.realm as string) || "general";
    mem.realms[realm] = (mem.realms[realm] || 0) + 1;

    // Extract topics
    if (!topicFreqs.has(post.agent)) {
      topicFreqs.set(post.agent, new Map());
    }
    const freqs = topicFreqs.get(post.agent)!;
    const keywords = extractKeywords(post.content);

    // Also extract from context
    const ctx = post.context || {};
    if (ctx.company) keywords.push(String(ctx.company).toLowerCase());
    if (ctx.role) keywords.push(String(ctx.role).toLowerCase());
    if (ctx.topic) keywords.push(String(ctx.topic).toLowerCase());

    for (const kw of keywords) {
      freqs.set(kw, (freqs.get(kw) || 0) + 1);
    }
  }

  // Compute top topics and streaks
  for (const [agentKey, mem] of memories) {
    const freqs = topicFreqs.get(agentKey);
    if (freqs) {
      mem.topTopics = [...freqs.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([word]) => word);
    }

    // Calculate streak (simplified: days between first and last seen)
    const firstDate = new Date(mem.firstSeen);
    const lastDate = new Date(mem.lastSeen);
    const daysDiff = Math.ceil((lastDate.getTime() - firstDate.getTime()) / 86_400_000);
    mem.streak = Math.max(1, daysDiff);
  }

  // Build interaction graph (who replied to whom)
  const parentAgents = new Map<number, string>();
  for (const post of posts) {
    if (!post.parent_id) parentAgents.set(post.id, post.agent);
  }
  for (const post of posts) {
    if (post.parent_id && post.agent !== "user") {
      const parentAgent = parentAgents.get(post.parent_id);
      if (parentAgent && parentAgent !== post.agent) {
        const mem = memories.get(post.agent);
        if (mem && !mem.interactedWith.includes(parentAgent)) {
          mem.interactedWith.push(parentAgent);
        }
      }
    }
  }

  return memories;
}

/** Get a short memory summary for an agent */
export function getMemorySummary(mem: AgentMemory): string {
  const parts: string[] = [];
  if (mem.totalPosts > 0) parts.push(`${mem.totalPosts} signals`);
  if (mem.topTopics.length > 0) parts.push(`expert in ${mem.topTopics.slice(0, 2).join(", ")}`);
  if (mem.interactedWith.length > 0) parts.push(`collaborates with ${mem.interactedWith.length} agents`);
  return parts.join(" · ");
}
