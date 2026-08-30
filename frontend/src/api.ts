import type {
  CaseInfo,
  CreateRunPayload,
  HealthResponse,
  ResearchReport,
  RunStatus,
  RunEvent,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Keep the HTTP fallback when the response is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function fetchCases(): Promise<CaseInfo[]> {
  return request<CaseInfo[]>("/api/cases");
}

export function fetchRuns(): Promise<RunStatus[]> {
  return request<RunStatus[]>("/api/runs");
}

export function fetchRun(runId: string): Promise<RunStatus> {
  return request<RunStatus>(`/api/runs/${encodeURIComponent(runId)}`);
}

export function fetchRunEvents(runId: string, afterSequence = 0): Promise<RunEvent[]> {
  return request<RunEvent[]>(
    `/api/runs/${encodeURIComponent(runId)}/events?after_sequence=${afterSequence}`,
  );
}

export function createRun(payload: CreateRunPayload): Promise<RunStatus> {
  return request<RunStatus>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchReport(runId: string): Promise<ResearchReport> {
  return request<ResearchReport>(
    `/api/runs/${encodeURIComponent(runId)}/report`
  );
}
