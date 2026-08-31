import type { RunEvent } from "./types";

export function activityDetailsLabel(event: RunEvent): string {
  return event.kind === "tool_start" || event.kind === "tool_result"
    ? "展开工具调用"
    : "展开阶段详情";
}

export function reduceRunEvents(existing: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const bySequence = new Map(existing.map((event) => [event.sequence, event]));
  for (const event of incoming) {
    if (event.tool_call_id) {
      for (const [sequence, previous] of bySequence) {
        if (previous.tool_call_id === event.tool_call_id && previous.kind === "tool_start") {
          bySequence.delete(sequence);
        }
      }
    }
    if (!bySequence.has(event.sequence)) bySequence.set(event.sequence, event);
  }
  return [...bySequence.values()].sort((a, b) => a.sequence - b.sequence);
}
