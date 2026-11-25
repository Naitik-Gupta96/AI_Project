// Shapes sent by the Python server (src/ai_project/server, blackboard/models.py).

export type Tag = "INIT" | "RATIFY" | "REVISE" | "REFUTE" | "REJECT";
export type Status = "INITIALIZED" | "RUNNING" | "CONSENSUS" | "DEADLOCK" | "FAILED";

export interface Judgment {
  prediction_matches: boolean;
  explanation_agrees: boolean;
  changed: boolean;
}

export interface MessageRecord {
  iteration: number;
  message_id: string;
  agent_id: string;
  tag: Tag;
  prediction: string;
  explanation: string;
  confidence: number | null;
  judgment: Judgment | null;
  in_reply_to: string | null;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export type EventKind =
  | "task"
  | "message"
  | "status"
  | "weight"
  | "context_revision"
  | "intervention"
  | "activation"
  | "collision"
  | "tool"
  | "format_error";

export interface BoardEvent {
  seq: number;
  kind: EventKind;
  data: Record<string, any>;
  timestamp: string;
}

export interface Position {
  prediction: string;
  explanation: string;
  source: string;
}

export interface BoardState {
  task: string;
  status: Status;
  version: number;
  iteration: number;
  agents: string[];
  weights: Record<string, number>;
  positions: Record<string, Position>;
  latest_message: MessageRecord | null;
  metadata: Record<string, any>;
}

export interface Activation {
  agent_id: string;
  score: number;
  eligible: boolean;
  reasons: string[];
}

export interface Candidate {
  tag: Tag;
  prediction: string;
  explanation: string;
  confidence: number | null;
  judgment: Judgment | null;
  rationale: string;
}

export interface Branch {
  branch_id: string;
  agent_id: string;
  target: MessageRecord;
  candidate: Candidate;
  lesson: string;
  status: Status;
  final_prediction: string | null;
  proximity: number;
  credit: number;
  messages: MessageRecord[];
}

export interface Intervention {
  applied: boolean;
  agent_id: string | null;
  chosen_branch: string | null;
  credit: number;
  lesson: string;
  proximity_before: number;
  weight_before: number | null;
  weight_after: number | null;
  branches: Branch[];
  reason: string;
  at_iteration: number;
}

export type StreamMessage =
  | { type: "board"; event: BoardEvent }
  | { type: "cf"; kind: string; data: Record<string, any> }
  | { type: "end"; result: SessionResult | null; stored?: boolean }
  | { type: "error"; message: string };

export interface SessionResult {
  session_id: string;
  status: Status;
  final_prediction: string | null;
  score: { correct: boolean; value: number; detail: Record<string, unknown> } | null;
  consensus: boolean;
  recovered: boolean;
  convergence_success: boolean;
  messages: number;
  rounds: number;
  collisions: number;
  format_errors: number;
  intelligibility: { session: string; per_agent: Record<string, string> };
  intelligibility_after_intervention: { session: string; per_agent: Record<string, string> } | null;
  usage: { total: { calls: number; prompt_tokens: number; completion_tokens: number; reported: boolean } };
  runtime_ms: number;
}

export interface SessionSummary {
  id: string;
  state: "created" | "running" | "finished" | "error" | "stored";
  paused?: boolean;
  status: Status | null;
  task_id?: string;
  question?: string;
  options?: string[];
  provider?: string;
  agents?: string[];
  cf_agents?: string[];
  messages?: number;
}

export interface Evidence {
  scores: Record<string, number>;
  objections: Record<string, string>;
}

export interface CatalogTask {
  task_id: string;
  question: string;
  options: string[];
  domain: string;
  roles: string[];
  evidence?: Record<string, Evidence>;
}

export interface Catalog {
  benchmarks: { name: string; available: boolean; reason?: string; tasks: CatalogTask[] }[];
}

export interface ProviderOption {
  spec: string;
  label: string;
}
