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
  source_mode: "verified_case" | "authoritative_online";
  subject: string | null;
  ticker: string | null;
  industry_id: string | null;
  research_question: string | null;
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

export interface RunEvent {
  event_id: string;
  run_id: string;
  sequence: number;
  occurred_at: string;
  kind: "stage" | "tool_start" | "tool_result" | "warning" | "error";
  tool_name: string | null;
  tool_call_id: string | null;
  title: string;
  summary: string;
  status: "running" | "success" | "warning" | "failed";
  duration_ms: number | null;
  source_ids: string[];
  public_details: Record<string, string | number | boolean>;
}

export interface CreateRunPayload {
  source_mode: "verified_case" | "authoritative_online";
  case_id?: string;
  subject?: string;
  ticker?: string;
  industry_id?: string;
  research_question?: string;
  cutoff_date: string;
}

export interface Evidence {
  evidence_id: string;
  doc_id: string;
  source_title: string | null;
  publisher: string | null;
  source_url: string | null;
  source_type: string | null;
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

export interface NarrativeSegment {
  segment_id: string;
  text: string;
  evidence_ids: string[];
  claim_type: "fact" | "change" | "analysis" | "risk" | "unresolved";
  status: "pass" | "review";
}

export interface NarrativeBlock {
  section: string;
  segments?: NarrativeSegment[];
  text?: string;
  evidence_ids?: string[];
}

export interface InvestmentDecisionSupport {
  stance: "值得深入跟踪" | "中性观察" | "当前证据不足";
  horizon: string;
  thesis: string[];
  catalysts: string[];
  risks: string[];
  entry_conditions: string[];
  invalidation_conditions: string[];
  data_gaps: string[];
  valuation_status: "not_available" | "available";
  confidence: number;
}

export interface ResearchReport {
  run_id: string;
  company_name: string;
  industry_id: string;
  cutoff_date: string;
  summary: string[];
  narrative?: NarrativeBlock[];
  investment_view?: InvestmentDecisionSupport | null;
  claims: Claim[];
  risks: Claim[];
  unresolved_items: Claim[];
  evidence_index: Evidence[];
  validation_issues: ValidationIssue[];
  generated_at: string;
  report_version: string;
}
