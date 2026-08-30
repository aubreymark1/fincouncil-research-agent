import { useEffect, useRef, useState } from "react";
import { fetchRunEvents } from "../api";
import { reduceRunEvents } from "../runEvents";
import type { RunEvent } from "../types";

interface RunActivityProps {
  runId: string;
  active: boolean;
}

function statusLabel(status: RunEvent["status"]): string {
  if (status === "running") return "进行中";
  if (status === "success") return "完成";
  if (status === "failed") return "失败";
  return "提示";
}

export function RunActivity({ runId, active }: RunActivityProps) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const lastSequence = useRef(0);

  useEffect(() => {
    setEvents([]);
    setError(null);
    lastSequence.current = 0;
    let cancelled = false;
    let source: EventSource | null = null;
    let timer: number | undefined;

    const append = (next: RunEvent[]) => {
      if (!cancelled) {
        setEvents((current) => reduceRunEvents(current, next));
        lastSequence.current = Math.max(lastSequence.current, ...next.map((item) => item.sequence));
      }
    };

    const poll = async () => {
      try {
        const current = await fetchRunEvents(runId, lastSequence.current);
        append(current);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "无法读取研究活动");
      }
    };

    void poll();
    if (active) {
      timer = window.setInterval(() => void poll(), 2000);
      try {
        source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events/stream`);
        source.addEventListener("run_event", (event) => {
          append([JSON.parse((event as MessageEvent).data) as RunEvent]);
        });
        source.onerror = () => source?.close();
      } catch {
        // Polling remains the supported fallback when EventSource is unavailable.
      }
    }

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearInterval(timer);
      source?.close();
    };
  }, [runId, active]);

  return (
    <section className="panel activity-panel" aria-label="研究活动">
      <div className="section-heading">
        <div>
          <div className="section-kicker">研究活动</div>
          <h2>系统正在做什么</h2>
        </div>
        <span className="section-note">真实阶段与工具记录</span>
      </div>
      {error && <p className="activity-error">{error}</p>}
      {events.length === 0 ? (
        <p className="muted">等待第一条研究活动…</p>
      ) : (
        <ol className="activity-list">
          {events.map((event) => (
            <li key={event.event_id} className={`activity-item ${event.status}`}>
              <span className="activity-marker" aria-hidden="true">{event.status === "success" ? "✓" : event.status === "failed" ? "!" : "·"}</span>
              <div className="activity-copy">
                <div className="activity-title-row">
                  <strong>{event.title}</strong>
                  <span>{statusLabel(event.status)}</span>
                </div>
                <p>{event.summary}</p>
                <small>
                  {new Date(event.occurred_at).toLocaleTimeString("zh-CN", { hour12: false })}
                  {event.duration_ms !== null ? ` · ${event.duration_ms} ms` : ""}
                </small>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
