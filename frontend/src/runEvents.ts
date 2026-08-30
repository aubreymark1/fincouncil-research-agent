import type { RunEvent } from "./types";

export function reduceRunEvents(existing: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const bySequence = new Map(existing.map((event) => [event.sequence, event]));
  for (const event of incoming) {
    if (!bySequence.has(event.sequence)) bySequence.set(event.sequence, event);
  }
  return [...bySequence.values()].sort((a, b) => a.sequence - b.sequence);
}
