export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  llm_available: boolean;
}

export interface CaseInfo {
  case_id: string;
  display_name: string;
  description: string;
  default_cutoff: string;
  supports_llm: boolean;
}

export interface RunStatus {
  run_id: string;
  case_id: string;
  status: "queued" | "running" | "success" | "failed";
  mode: string;
  llm_enabled: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  stage: string | null;
  progress: string[];
  report_ready: boolean;
  download: {
    report_json: string;
    report_md: string;
  };
}

export interface CreateRunPayload {
  case_id: string;
  cutoff_date: string;
  llm_enabled?: boolean;
}

export interface Evidence {
  evidence_id: string;
  doc_id: string;
  chunk_id: string;
  fact_text: string;
  quote: string;
  published_at: string;
  page: number | null;
  section: string | null;
  locator: string;
  company_name: string | null;
  industry_id: string | null;
  evidence_type: string;
  confidence: number;
  review_status: "verified" | "pending" | "rejected";
}

export interface Claim {
  claim_id: string;
  text: string;
  claim_type: "fact" | "change" | "analysis" | "risk" | "unresolved";
  risk_severity: "low" | "medium" | "high" | null;
  evidence_ids: string[];
  calculation: string | null;
  confidence: number;
  industry_metric_ids: string[];
  status: "draft" | "pass" | "review" | "reject";
}

export interface ValidationIssue {
  issue_id: string;
  check_name: string;
  severity: "info" | "warning" | "error" | "critical";
  issue_type: string;
  message: string;
  claim_id: string | null;
  evidence_id: string | null;
  report_section: string | null;
  rerun_required: boolean;
  human_confirmation_required: boolean;
  status: "open" | "resolved" | "accepted_risk";
}

export interface NarrativeSection {
  section: string;
  text: string;
  evidence_ids?: string[];
}

export interface ResearchReport {
  run_id: string;
  company_name: string;
  industry_id: string;
  cutoff_date: string;
  summary: string[];
  narrative?: NarrativeSection[];
  claims: Claim[];
  risks: Claim[];
  unresolved_items: Claim[];
  evidence_index: Evidence[];
  validation_issues: ValidationIssue[];
  generated_at: string;
  report_version: string;
}
