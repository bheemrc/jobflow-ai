import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  JobResult,
  AgentState,
  ApprovalItem,
  LeetCodeProgress,
  PipelineJob,
  ActivityLogEntry,
  BotState,
  BotRun,
  BotLogEntry,
  TokenUsageSummary,
} from "./types";

interface SearchSlice {
  searchTerm: string;
  location: string;
  sites: string[];
  resultsWanted: number;
  isRemote: boolean;
  hoursOld: number | null;
  results: JobResult[];
  savedUrls: string[];
  selectedSearchJobIndex: number | null;
  setSearchTerm: (v: string) => void;
  setLocation: (v: string) => void;
  setSites: (v: string[] | ((prev: string[]) => string[])) => void;
  setResultsWanted: (v: number) => void;
  setIsRemote: (v: boolean) => void;
  setHoursOld: (v: number | null) => void;
  setResults: (v: JobResult[]) => void;
  addSavedUrl: (url: string) => void;
  setSelectedSearchJobIndex: (v: number | null) => void;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  actions?: { label: string; type: string; value: string }[];
  sections?: string[];
  isLoading?: boolean;
  showUpload?: boolean;
  thinking?: string;
  toolProgress?: { active: string[]; completed: string[] };
  toolEvents?: { type: "start" | "end"; tool: string; agent?: string; input?: string; output?: string }[];
  agentEvents?: { agent: string; status: "start" | "end" }[];
  agentStreams?: Record<string, string>;
  approvalNeeded?: {
    approval_id?: number;
    type: string;
    title: string;
    agent: string;
    content: string;
    priority: string;
  };
  sectionCards?: {
    card_type: string;
    title: string;
    agent: string;
    content: string;
    data?: Record<string, unknown>;
  }[];
}

interface CoachSlice {
  resumeId: string | null;
  coachSessionId: string | null;
  chatMessages: ChatMessage[];
  setResumeId: (v: string | null) => void;
  setCoachSessionId: (v: string | null) => void;
  setChatMessages: (v: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  clearChat: () => void;
}

export interface FocusRoom {
  id: string;
  topic: string;
  createdAt: number;
  messages: ChatMessage[];
}

const MAX_ROOMS = 5;
const MAX_ROOM_MESSAGES = 50;

interface RoomsSlice {
  rooms: FocusRoom[];
  activeRoomId: string;
  createRoom: (topic: string) => string;
  deleteRoom: (roomId: string) => void;
  setActiveRoom: (roomId: string) => void;
  setRoomMessages: (roomId: string, v: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
}

interface PreferencesSlice {
  savedJobsView: "grid" | "table";
  setSavedJobsView: (v: "grid" | "table") => void;
}

interface AgentSlice {
  agents: AgentState[];
  setAgents: (agents: AgentState[]) => void;
  updateAgentStatus: (id: string, status: string) => void;
}

interface ApprovalSlice {
  approvals: ApprovalItem[];
  setApprovals: (items: ApprovalItem[]) => void;
  removeApproval: (id: number) => void;
}

interface LeetCodeSlice {
  leetcodeProgress: LeetCodeProgress | null;
  setLeetcodeProgress: (p: LeetCodeProgress) => void;
}

interface PipelineSlice {
  pipelineJobs: Record<string, PipelineJob[]>;
  setPipelineJobs: (jobs: Record<string, PipelineJob[]>) => void;
}

interface ActivitySlice {
  activityLog: ActivityLogEntry[];
  setActivityLog: (entries: ActivityLogEntry[]) => void;
}

interface BotSlice {
  botStates: BotState[];
  botRuns: Record<string, BotRun[]>;
  tokenUsage: TokenUsageSummary | null;
  botLogs: Record<string, BotLogEntry[]>;
  setBotStates: (bots: BotState[]) => void;
  updateBotState: (name: string, update: Partial<BotState>) => void;
  addBotRun: (run: BotRun) => void;
  updateBotRun: (runId: string, update: Partial<BotRun>) => void;
  setTokenUsage: (usage: TokenUsageSummary) => void;
  appendBotLog: (runId: string, log: BotLogEntry) => void;
  setBotRuns: (botName: string, runs: BotRun[]) => void;
}

interface OnboardingSlice {
  onboardingComplete: boolean;
  onboardingStep: number;
  userPreferredRole: string;
  userPreferredLocation: string;
  userWantsRemote: boolean;
  setOnboardingComplete: (v: boolean) => void;
  setOnboardingStep: (v: number) => void;
  setUserPreferredRole: (v: string) => void;
  setUserPreferredLocation: (v: string) => void;
  setUserWantsRemote: (v: boolean) => void;
}

export type AppStore = SearchSlice &
  CoachSlice &
  RoomsSlice &
  PreferencesSlice &
  AgentSlice &
  ApprovalSlice &
  LeetCodeSlice &
  PipelineSlice &
  ActivitySlice &
  BotSlice &
  OnboardingSlice;

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      // Search
      searchTerm: "",
      location: "",
      sites: ["indeed", "linkedin"],
      resultsWanted: 20,
      isRemote: false,
      hoursOld: null,
      results: [],
      savedUrls: [],
      selectedSearchJobIndex: null,
      setSearchTerm: (v) => set({ searchTerm: v }),
      setLocation: (v) => set({ location: v }),
      setSites: (v) =>
        set((state) => ({
          sites: typeof v === "function" ? v(state.sites) : v,
        })),
      setResultsWanted: (v) => set({ resultsWanted: v }),
      setIsRemote: (v) => set({ isRemote: v }),
      setHoursOld: (v) => set({ hoursOld: v }),
      setResults: (v) => set({ results: v, selectedSearchJobIndex: null }),
      addSavedUrl: (url) =>
        set((state) => ({
          savedUrls: state.savedUrls.includes(url)
            ? state.savedUrls
            : [...state.savedUrls, url],
        })),
      setSelectedSearchJobIndex: (v) => set({ selectedSearchJobIndex: v }),

      // Coach
      resumeId: null,
      coachSessionId: null,
      chatMessages: [],
      setResumeId: (v) => set({ resumeId: v }),
      setCoachSessionId: (v) => set({ coachSessionId: v }),
      setChatMessages: (v) =>
        set((state) => ({
          chatMessages: typeof v === "function" ? v(state.chatMessages) : v,
        })),
      clearChat: () => set({ chatMessages: [], coachSessionId: null }),

      // Focus Rooms
      rooms: [],
      activeRoomId: "main",
      createRoom: (topic) => {
        const id = Array.from(crypto.getRandomValues(new Uint8Array(8)))
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");
        set((state) => {
          if (state.rooms.length >= MAX_ROOMS) return state;
          return {
            rooms: [
              ...state.rooms,
              { id, topic, createdAt: Date.now(), messages: [] },
            ],
            activeRoomId: id,
          };
        });
        return id;
      },
      deleteRoom: (roomId) =>
        set((state) => ({
          rooms: state.rooms.filter((r) => r.id !== roomId),
          activeRoomId: state.activeRoomId === roomId ? "main" : state.activeRoomId,
        })),
      setActiveRoom: (roomId) => set({ activeRoomId: roomId }),
      setRoomMessages: (roomId, v) =>
        set((state) => ({
          rooms: state.rooms.map((r) =>
            r.id === roomId
              ? {
                  ...r,
                  messages: (typeof v === "function" ? v(r.messages) : v).slice(
                    -MAX_ROOM_MESSAGES
                  ),
                }
              : r
          ),
        })),

      // Preferences
      savedJobsView: "grid",
      setSavedJobsView: (v) => set({ savedJobsView: v }),

      // Agents
      agents: [],
      setAgents: (agents) => set({ agents }),
      updateAgentStatus: (id, status) =>
        set((state) => ({
          agents: state.agents.map((a) =>
            a.agent_id === id ? { ...a, status: status as AgentState["status"] } : a
          ),
        })),

      // Approvals
      approvals: [],
      setApprovals: (items) => set({ approvals: items }),
      removeApproval: (id) =>
        set((state) => ({
          approvals: state.approvals.filter((a) => a.id !== id),
        })),

      // LeetCode
      leetcodeProgress: null,
      setLeetcodeProgress: (p) => set({ leetcodeProgress: p }),

      // Pipeline
      pipelineJobs: {},
      setPipelineJobs: (jobs) => set({ pipelineJobs: jobs }),

      // Activity
      activityLog: [],
      setActivityLog: (entries) => set({ activityLog: entries }),

      // Bots
      botStates: [],
      botRuns: {},
      tokenUsage: null,
      botLogs: {},
      setBotStates: (bots) => set({ botStates: bots }),
      updateBotState: (name, update) =>
        set((state) => ({
          botStates: state.botStates.map((b) =>
            b.name === name ? { ...b, ...update } : b
          ),
        })),
      addBotRun: (run) =>
        set((state) => ({
          botRuns: {
            ...state.botRuns,
            [run.bot_name]: [run, ...(state.botRuns[run.bot_name] || [])].slice(0, 50),
          },
        })),
      updateBotRun: (runId, update) =>
        set((state) => {
          const newRuns = { ...state.botRuns };
          for (const [botName, runs] of Object.entries(newRuns)) {
            newRuns[botName] = runs.map((r) =>
              r.run_id === runId ? { ...r, ...update } : r
            );
          }
          return { botRuns: newRuns };
        }),
      setTokenUsage: (usage) => set({ tokenUsage: usage }),
      appendBotLog: (runId, log) =>
        set((state) => ({
          botLogs: {
            ...state.botLogs,
            [runId]: [...(state.botLogs[runId] || []), log].slice(-200),
          },
        })),
      setBotRuns: (botName, runs) =>
        set((state) => ({
          botRuns: { ...state.botRuns, [botName]: runs },
        })),

      // Onboarding
      onboardingComplete: false,
      onboardingStep: 0,
      userPreferredRole: "",
      userPreferredLocation: "",
      userWantsRemote: false,
      setOnboardingComplete: (v) => set({ onboardingComplete: v }),
      setOnboardingStep: (v) => set({ onboardingStep: v }),
      setUserPreferredRole: (v) => set({ userPreferredRole: v }),
      setUserPreferredLocation: (v) => set({ userPreferredLocation: v }),
      setUserWantsRemote: (v) => set({ userWantsRemote: v }),
    }),
    {
      name: "job-dashboard-store",
      skipHydration: true,
      partialize: (state) => ({
        searchTerm: state.searchTerm,
        location: state.location,
        sites: state.sites,
        resultsWanted: state.resultsWanted,
        isRemote: state.isRemote,
        hoursOld: state.hoursOld,
        results: state.results,
        savedUrls: state.savedUrls,
        selectedSearchJobIndex: state.selectedSearchJobIndex,
        resumeId: state.resumeId,
        coachSessionId: state.coachSessionId,
        chatMessages: state.chatMessages,
        rooms: state.rooms.map((r) => ({
          ...r,
          messages: r.messages.filter((m) => !m.isLoading).slice(-MAX_ROOM_MESSAGES),
        })),
        activeRoomId: state.activeRoomId,
        savedJobsView: state.savedJobsView,
        onboardingComplete: state.onboardingComplete,
        userPreferredRole: state.userPreferredRole,
        userPreferredLocation: state.userPreferredLocation,
        userWantsRemote: state.userWantsRemote,
      }),
    }
  )
);
