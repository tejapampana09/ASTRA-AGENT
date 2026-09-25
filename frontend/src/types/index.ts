export interface Task {
  task_id: string;
  goal: string;
  status: 'created' | 'running' | 'paused' | 'paused_for_approval' | 'completed' | 'failed' | 'cancelled' | 'timed_out' | 'stale';
  verification_status: 'pending' | 'verified' | 'failed' | 'uncertain' | 'partially_verified' | 'timed_out';
  workspace_path?: string;
  timeout_seconds?: number;
  heartbeat_at?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  error_message?: string;
  final_report?: FinalReport;
}

export interface FinalReport {
  task_id: string;
  status: string;
  goal: string;
  evidence: {
    tests: {
      passed: number;
      failed: number;
      errors: number;
      command: string;
    };
    build: string;
    files_changed_count: number;
    files_changed: string[];
    verification_evidence?: Record<string, any>;
  };
  git_diff: string;
  timeline: string[];
  iterations: number;
  retries: number;
  tool_calls?: Array<{
    tool_name?: string;
    command?: string;
    arguments?: any;
    result?: string;
    error?: string;
    duration_ms?: number;
  }>;
  decisions?: Array<{
    subject: string;
    decision: string;
  }>;
  failure_history?: Array<{
    category: string;
    error: string;
    hypothesis?: string;
    root_cause?: string;
  }>;
  commit?: {
    commit_sha?: string;
    commit_message?: string;
    branch?: string;
    conventional_prefix?: string;
  };
  pull_request?: {
    pr_number?: number;
    pr_url?: string;
    base_branch?: string;
    head_branch?: string;
    title?: string;
  };
  errors: string[];
}

export interface ApprovalTicket {
  id: string;
  task_id: string;
  tool_name: string;
  arguments: Record<string, any>;
  risk_level: 'READ' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

export interface AgentEvent {
  task_id: string;
  sequence_id?: number;
  event_type: string;
  source?: string;
  message: string;
  payload?: Record<string, any>;
  timestamp: string;
}

export interface TaskAuditReport {
  task_id: string;
  goal: string;
  status: string;
  verification_status: string;
  workspace_path?: string;
  timing: {
    created_at?: string;
    started_at?: string;
    completed_at?: string;
    timeout_seconds?: number;
  };
  timeline_events: AgentEvent[];
  decisions: any[];
  commands_and_tools: any[];
  files_touched: string[];
  git_diff?: string;
  empirical_verification: any;
  failure_and_retry_history: any[];
  commit?: any;
  pull_request?: any;
  token_usage_and_cost?: {
    total_tokens?: number;
    estimated_cost_usd?: number;
  };
}
