export interface Task {
  task_id: string;
  goal: string;
  status: 'created' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  verification_status: 'pending' | 'verified' | 'failed' | 'uncertain';
  workspace_path?: string;
  created_at: string;
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
  };
  git_diff: string;
  timeline: string[];
  iterations: number;
  retries: number;
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
  event_type: string;
  message: string;
  payload?: Record<string, any>;
  timestamp: string;
}
