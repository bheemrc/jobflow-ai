export type JobStatus = "saved" | "applied" | "interview" | "offer" | "rejected";

export interface JobResult {
  title: string;
  company: string;
  location: string;
  min_amount: number | null;
  max_amount: number | null;
  currency: string | null;
  job_url: string;
  date_posted: string | null;
  job_type: string | null;
  is_remote: boolean;
  description: string | null;
  site: string | null;
  employer_logo: string | null;
}

export interface SavedJob extends JobResult {
  id: number;
  status: JobStatus;
  notes: string;
  saved_at: string;
  updated_at: string;
}

export interface SearchParams {
  search_term?: string;
  location?: string;
  site_name?: string[];
  job_type?: string;
  is_remote?: boolean;
  results_wanted?: number;
  hours_old?: number;
}

// AI types

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
  timestamp: string;
  tool_calls: Record<string, unknown>[];
  suggestions: string[];
}

export interface JobMatch {
  job_title: string;
  company: string;
  score: number;
  explanation: string;
}

export interface RoleSuggestion {
  title: string;
  relevance: "high" | "medium" | "low";
  reason: string;
}

export interface LocationSuggestion {
  location: string;
  score: number;
  salary_range: string;
  cost_of_living: "low" | "medium" | "high";
  reason: string;
}

export type InterviewType =
  | "phone_screen"
  | "technical"
  | "behavioral"
  | "system_design"
  | "hiring_manager";

export interface InterviewPrepRequest {
  job_title: string;
  company: string;
  job_description?: string;
  resume_id?: string;
  interview_type: InterviewType;
}

export interface InterviewPrepResponse {
  session_id: string;
  prep: string;
}

export interface CompanyResearchRequest {
  company_name: string;
  job_title?: string;
}

export interface CompanyResearchResponse {
  session_id: string;
  research: string;
}

export interface ApplicationAnswersRequest {
  job_title: string;
  company: string;
  job_description: string;
  resume_id?: string;
  questions?: string;
}

export interface ApplicationAnswersResponse {
  session_id: string;
  answers: string;
}

// ── Dashboard types ──

export type AgentStatusType = "idle" | "running" | "waiting";

export interface AgentState {
  agent_id: string;
  status: AgentStatusType;
  last_run: string | null;
  current_task: string | null;
  tasks_completed: number;
}

export interface ApprovalItem {
  id: number;
  thread_id: string;
  type: string;
  title: string;
  agent: string;
  content: string;
  priority: string;
  status: string;
  created_at: string;
}

export interface PipelineJob {
  id: number;
  title: string;
  company: string;
  location: string;
  status: JobStatus;
  job_url: string;
  min_amount?: number | null;
  max_amount?: number | null;
  saved_at: string;
  updated_at: string;
}

export interface LeetCodeProgress {
  total_solved: number;
  total_attempted: number;
  streak: number;
  problems: LeetCodeProblem[];
  mastery: LeetCodeMastery[];
}

export interface LeetCodeProblem {
  id: number;
  problem_id: number;
  problem_title: string;
  difficulty: string;
  topic: string;
  solved: boolean;
  time_minutes: number | null;
  attempts: number;
}

export interface LeetCodeMastery {
  topic: string;
  level: number;
  problems_solved: number;
  problems_attempted: number;
}

export interface ActivityLogEntry {
  id: number;
  agent: string;
  action: string;
  detail: string | null;
  created_at: string;
}

// ── Bot types ──

export type BotStatus = "waiting" | "running" | "paused" | "stopped" | "errored" | "disabled" | "scheduled";

export interface BotState {
  name: string;
  display_name: string;
  description: string;
  status: BotStatus;
  enabled: boolean;
  last_run_at: string | null;
  cooldown_until: string | null;
  runs_today: number;
  max_runs_per_day: number;
  last_activated_by: string | null;
  total_runs: number;
  is_custom?: boolean;
  integrations?: Record<string, unknown>;
  last_output_preview?: string;
  last_run_cost?: number;
  last_run_status?: string;
  /** @deprecated Use cooldown_until instead */
  next_run_at?: string | null;
  config: {
    model?: string;
    temperature?: number;
    intent?: {
      cooldown_minutes: number;
      max_runs_per_day: number;
      signal_count: number;
    };
    heartbeat_hours?: number;
    requires_approval?: boolean;
    timeout_minutes?: number;
    /** @deprecated Replaced by intent */
    schedule?: {
      type: string;
      hours?: number;
      minutes?: number;
      hour?: number;
      minute?: number;
    };
  };
}

export interface BotTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  tools: string[];
  prompt: string;
  schedule_type: string;
  schedule_hours?: number;
  schedule_hour?: number;
  schedule_minute?: number;
  model: string;
  integrations: string[];
}

export interface AvailableTool {
  name: string;
  description: string;
  category: string;
}

export interface BotRun {
  run_id: string;
  bot_name: string;
  status: string;
  trigger_type: string;
  started_at: string;
  completed_at: string | null;
  output: string | null;
  input_tokens: number;
  output_tokens: number;
  cost: number;
}

export interface BotLogEntry {
  id: number;
  run_id: string;
  level: string;
  event_type: string;
  message: string;
  data: Record<string, unknown> | null;
  created_at: string;
}

export interface TokenUsageSummary {
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_runs: number;
  by_bot: Record<string, { cost: number; input_tokens: number; output_tokens: number; runs: number }>;
  daily: { date: string; cost: number; input_tokens: number; output_tokens: number; runs: number }[];
}

// ── Prep Materials types ──

export type PrepMaterialType = "interview" | "system_design" | "leetcode" | "company_research" | "general" | "tutorial";

export interface PrepResource {
  title: string;
  url: string;
  type: string;
}

export interface PrepMaterial {
  id: number;
  material_type: PrepMaterialType;
  title: string;
  company: string | null;
  role: string | null;
  agent_source: string | null;
  content: Record<string, unknown>;
  resources: PrepResource[];
  scheduled_date: string | null;
  created_at: string;
  updated_at: string;
}

// ── Journal Entry types ──

export type JournalEntryType = "insight" | "recommendation" | "summary" | "note" | "action_item";

export interface JournalEntry {
  id: number;
  entry_type: JournalEntryType;
  title: string;
  content: string;
  agent: string | null;
  priority: string;
  tags: string[];
  is_read: boolean;
  is_pinned: boolean;
  created_at: string;
}

export interface BotEvent {
  type: string;
  source: string;
  bot_name?: string;
  run_id?: string;
  status?: string;
  bots?: BotState[];
  error?: string;
  trigger_type?: string;
  duration_seconds?: number;
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
  output_preview?: string;
  timestamp?: string;
  [key: string]: unknown;
}

// ── Group Chat types ──

export type GroupChatStatus = "active" | "paused" | "concluded";

export interface GroupChatConfig {
  max_turns?: number;
  max_tokens?: number;
  turn_mode?: "mention_driven" | "round_robin" | "topic_signal";
  allowed_tools?: string[];
  allow_self_modification?: boolean;
  require_approval_for_changes?: boolean;
}

export interface GroupChat {
  id: number;
  topic: string;
  status: GroupChatStatus;
  participants: string[];
  initiator: string;
  max_turns: number;
  max_tokens: number;
  turns_used: number;
  tokens_used: number;
  config: GroupChatConfig;
  user_id: string;
  created_at: string;
  concluded_at: string | null;
  summary: string | null;
}

export interface GroupChatMessage {
  id: number;
  group_chat_id: number;
  timeline_post_id?: number;
  agent: string;
  turn_number: number;
  mentions: string[];
  tokens_used: number;
  user_id: string;
  created_at: string;
  content: string;
  post_type?: string;
  context?: {
    turn?: number;
    topic?: string;
    mentions?: string[];
    group_chat_id?: number;
  };
}

export interface GroupChatEvent {
  type: string;
  group_chat_id?: number;
  agent?: string;
  content?: string;
  mentions?: string[];
  turn?: number;
  post_id?: number;
  topic?: string;
  participants?: string[];
  turns_used?: number;
  tokens_used?: number;
  summary?: string;
  error?: string;
  message?: string;
  turn_percentage?: number;
  token_percentage?: number;
  timestamp?: string;
  // For participant_joined events (especially dynamic agents)
  reason?: string;
  display_name?: string;
  role?: string;
  is_dynamic?: boolean;
  // For tool call events
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  result_preview?: string;
  [key: string]: unknown;
}
