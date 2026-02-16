"use client";

import { useState, useRef, useCallback } from "react";

export type AgentRole = "alpha" | "beta" | "gamma";
export type AgentStatus = "idle" | "waiting" | "thinking" | "streaming" | "done" | "error";

export interface ArenaAgent {
  role: AgentRole;
  name: string;
  title: string;
  status: AgentStatus;
  content: string;
  thinkingMessage: string;
  startedAt?: number;
  finishedAt?: number;
  error?: string;
  wordCount: number;
}

export interface ArenaSession {
  topic: string;
  status: "idle" | "running" | "complete" | "error";
  startedAt?: number;
}

const AGENT_CONFIG: Record<AgentRole, { name: string; title: string }> = {
  alpha: { name: "Alpha", title: "The Pioneer" },
  beta: { name: "Beta", title: "The Challenger" },
  gamma: { name: "Gamma", title: "The Arbiter" },
};

const THINKING_MESSAGES: Record<AgentRole, string[]> = {
  alpha: [
    "Analyzing the problem space...",
    "Researching approaches...",
    "Formulating initial response...",
    "Building my analysis...",
  ],
  beta: [
    "Reviewing Alpha's work...",
    "Identifying weaknesses...",
    "Preparing a stronger approach...",
    "I can definitely do better...",
  ],
  gamma: [
    "Studying both perspectives...",
    "Cross-referencing claims...",
    "Synthesizing the best elements...",
    "Crafting the definitive answer...",
  ],
};

function buildPrompt(role: AgentRole, topic: string, alphaContent?: string, betaContent?: string): string {
  switch (role) {
    case "alpha":
      return [
        "You are Agent Alpha — The Pioneer. You are the FIRST to tackle this research question.",
        "Your job is to provide a thorough, well-structured initial analysis.",
        "Be bold, be comprehensive, and present your findings with confidence.",
        "Use markdown formatting with headers, bullet points, and clear structure.",
        "Keep your response focused and substantive (aim for 300-500 words).",
        "",
        `Research question: ${topic}`,
      ].join("\n");

    case "beta":
      return [
        "You are Agent Beta — The Challenger. You've just reviewed Agent Alpha's work below.",
        "Your mission: IMPROVE upon it. Find gaps, correct errors, add depth.",
        "Start with a brief assessment of Alpha's work, then present YOUR superior version.",
        "Be competitive but constructive. Show why your approach is better.",
        "Use markdown formatting. Keep your response focused (aim for 300-500 words).",
        "",
        `Original question: ${topic}`,
        "",
        "--- AGENT ALPHA'S RESPONSE ---",
        alphaContent || "",
        "--- END OF ALPHA'S RESPONSE ---",
        "",
        "Now provide your improved analysis. Start with what Alpha missed or got wrong, then deliver your better answer.",
      ].join("\n");

    case "gamma":
      return [
        "You are Agent Gamma — The Arbiter. You have reviewed BOTH previous agents' work.",
        "Your mission: Create the DEFINITIVE, final answer by synthesizing the best from both.",
        "Resolve any contradictions, fill remaining gaps, and produce the ultimate response.",
        "This is the version the user will rely on. Make it exceptional.",
        "Use markdown formatting with clear structure. Keep it focused (aim for 400-600 words).",
        "",
        `Original question: ${topic}`,
        "",
        "--- AGENT ALPHA (The Pioneer) ---",
        alphaContent || "",
        "--- END ALPHA ---",
        "",
        "--- AGENT BETA (The Challenger) ---",
        betaContent || "",
        "--- END BETA ---",
        "",
        "Now deliver the definitive answer. Acknowledge what each agent did well, resolve disputes, and present the authoritative final version.",
      ].join("\n");
  }
}

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function createAgent(role: AgentRole): ArenaAgent {
  const config = AGENT_CONFIG[role];
  return {
    role,
    name: config.name,
    title: config.title,
    status: "idle",
    content: "",
    thinkingMessage: "",
    wordCount: 0,
  };
}

async function streamFromArena(
  message: string,
  onDelta: (text: string) => void,
  onComplete: (fullText: string) => void,
  onError: (error: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const res = await fetch("/api/arena/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `API error: ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";
    let fullText = "";

    const processLine = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data: ")) return;

      try {
        const data = JSON.parse(trimmed.slice(6));

        if (data.type === "delta" && data.text) {
          fullText += data.text;
          onDelta(data.text);
        } else if (data.type === "done") {
          // Stream finished
        } else if (data.type === "error") {
          onError(data.message || "Unknown error");
        }
      } catch {
        // Skip malformed JSON
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        processLine(line);
      }
    }

    // Process any remaining data in the buffer
    if (buffer.trim()) {
      processLine(buffer);
    }

    onComplete(fullText);
  } catch (err) {
    if (signal?.aborted) return;
    onError(err instanceof Error ? err.message : "Stream failed");
  }
}

export function useArenaSession() {
  const [session, setSession] = useState<ArenaSession | null>(null);
  const [agents, setAgents] = useState<ArenaAgent[]>([
    createAgent("alpha"),
    createAgent("beta"),
    createAgent("gamma"),
  ]);

  const abortRef = useRef<AbortController | null>(null);
  const thinkingIntervalRef = useRef<ReturnType<typeof setInterval>>(undefined);
  const contentRef = useRef<Record<AgentRole, string>>({ alpha: "", beta: "", gamma: "" });

  const updateAgent = useCallback((role: AgentRole, updates: Partial<ArenaAgent>) => {
    setAgents((prev) =>
      prev.map((a) => (a.role === role ? { ...a, ...updates } : a))
    );
  }, []);

  const cycleThinkingMessage = useCallback((role: AgentRole) => {
    const messages = THINKING_MESSAGES[role];
    let i = 0;
    return setInterval(() => {
      i = (i + 1) % messages.length;
      updateAgent(role, { thinkingMessage: messages[i] });
    }, 2500);
  }, [updateAgent]);

  const runAgent = useCallback(
    async (
      role: AgentRole,
      topic: string,
      signal: AbortSignal,
    ): Promise<string> => {
      return new Promise((resolve, reject) => {
        const prompt = buildPrompt(
          role,
          topic,
          contentRef.current.alpha,
          contentRef.current.beta,
        );

        // Generate unique session ID per agent
        const sessionId = `arena-${role}-${Date.now()}`;

        // Start thinking state
        updateAgent(role, {
          status: "thinking",
          startedAt: Date.now(),
          thinkingMessage: THINKING_MESSAGES[role][0],
          content: "",
          error: undefined,
        });

        const interval = cycleThinkingMessage(role);

        // Batch delta updates: accumulate in local var, flush to React once per frame
        let accumulated = "";
        let rafId = 0;

        streamFromArena(
          prompt,
          // onDelta — called on every token, but we batch state updates
          (text) => {
            accumulated += text;
            if (!rafId) {
              rafId = requestAnimationFrame(() => {
                rafId = 0;
                updateAgent(role, {
                  status: "streaming",
                  content: accumulated,
                  wordCount: countWords(accumulated),
                });
              });
            }
          },
          // onComplete
          (fullText) => {
            if (rafId) cancelAnimationFrame(rafId);
            clearInterval(interval);
            contentRef.current[role] = fullText;
            updateAgent(role, {
              status: "done",
              content: fullText,
              finishedAt: Date.now(),
              wordCount: countWords(fullText),
            });
            resolve(fullText);
          },
          // onError
          (error) => {
            clearInterval(interval);
            updateAgent(role, {
              status: "error",
              error,
              finishedAt: Date.now(),
            });
            reject(new Error(error));
          },
          signal,
        );
      });
    },
    [updateAgent, cycleThinkingMessage],
  );

  const startArena = useCallback(
    async (topic: string) => {
      // Abort any previous session
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Reset state
      contentRef.current = { alpha: "", beta: "", gamma: "" };
      setAgents([createAgent("alpha"), createAgent("beta"), createAgent("gamma")]);
      setSession({ topic, status: "running", startedAt: Date.now() });

      // Set waiting states
      updateAgent("beta", { status: "waiting" });
      updateAgent("gamma", { status: "waiting" });

      try {
        // Run Alpha
        await runAgent("alpha", topic, controller.signal);
        if (controller.signal.aborted) return;

        // Run Beta
        updateAgent("gamma", { status: "waiting" });
        await runAgent("beta", topic, controller.signal);
        if (controller.signal.aborted) return;

        // Run Gamma
        await runAgent("gamma", topic, controller.signal);
        if (controller.signal.aborted) return;

        setSession((prev) => (prev ? { ...prev, status: "complete" } : prev));
      } catch {
        if (!controller.signal.aborted) {
          setSession((prev) => (prev ? { ...prev, status: "error" } : prev));
        }
      }
    },
    [runAgent, updateAgent],
  );

  const stopArena = useCallback(() => {
    abortRef.current?.abort();
    if (thinkingIntervalRef.current) clearInterval(thinkingIntervalRef.current);
    setSession((prev) => (prev ? { ...prev, status: "error" } : prev));
    setAgents((prev) =>
      prev.map((a) =>
        a.status === "thinking" || a.status === "streaming" || a.status === "waiting"
          ? { ...a, status: "idle" }
          : a
      )
    );
  }, []);

  const resetArena = useCallback(() => {
    abortRef.current?.abort();
    if (thinkingIntervalRef.current) clearInterval(thinkingIntervalRef.current);
    contentRef.current = { alpha: "", beta: "", gamma: "" };
    setSession(null);
    setAgents([createAgent("alpha"), createAgent("beta"), createAgent("gamma")]);
  }, []);

  return {
    session,
    agents,
    startArena,
    stopArena,
    resetArena,
  };
}
