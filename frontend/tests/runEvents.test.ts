import assert from "node:assert/strict";
import { reduceRunEvents } from "../src/runEvents.ts";
import type { RunEvent } from "../src/types.ts";

const base = (updates: Partial<RunEvent>): RunEvent => ({
  event_id: updates.event_id ?? "EVT-1",
  run_id: "RUN-WB-1",
  sequence: updates.sequence ?? 1,
  occurred_at: "2026-08-31T00:00:00Z",
  kind: updates.kind ?? "stage",
  tool_name: updates.tool_name ?? null,
  tool_call_id: updates.tool_call_id ?? null,
  title: updates.title ?? "准备研究",
  summary: updates.summary ?? "完成",
  status: updates.status ?? "success",
  duration_ms: updates.duration_ms ?? null,
  source_ids: updates.source_ids ?? [],
  public_details: updates.public_details ?? {},
});

const first = base({ sequence: 1 });
const second = base({ sequence: 2, event_id: "EVT-2", title: "检索完成", duration_ms: 840 });
const duplicate = base({ sequence: 1, event_id: "EVT-1-duplicate", summary: "不应重复" });

assert.deepEqual(reduceRunEvents([], [second, first, duplicate]).map((item) => item.sequence), [1, 2]);
assert.equal(reduceRunEvents([], [second, first, duplicate])[0].summary, "完成");

const toolStart = base({ sequence: 3, event_id: "EVT-3", kind: "tool_start", tool_name: "search_company_filings", tool_call_id: "CALL-1", status: "running", title: "检索公告", summary: "开始检索" });
const toolResult = base({ sequence: 4, event_id: "EVT-4", kind: "tool_result", tool_name: "search_company_filings", tool_call_id: "CALL-1", status: "success", title: "检索完成", summary: "找到 4 份资料" });
const merged = reduceRunEvents([], [toolStart, toolResult]);
assert.equal(merged.length, 1);
assert.equal(merged[0].event_id, "EVT-4");
assert.equal(merged[0].status, "success");

console.log("run event behavior tests passed");
