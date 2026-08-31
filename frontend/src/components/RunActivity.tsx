import { useEffect, useRef, useState } from "react";
import { fetchRunEvents } from "../api";
import { activityDetailsLabel, reduceRunEvents } from "../runEvents";
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
    let fallbackStarted = false;

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
      try {
        source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events/stream`);
        source.addEventListener("run_event", (event) => {
          append([JSON.parse((event as MessageEvent).data) as RunEvent]);
        });
        source.onerror = () => {
          source?.close();
          if (!fallbackStarted && !cancelled) {
            fallbackStarted = true;
            timer = window.setInterval(() => void poll(), 2500);
          }
        };
      } catch {
        fallbackStarted = true;
        timer = window.setInterval(() => void poll(), 2500);
      }
    }

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearInterval(timer);
      source?.close();
    };
  }, [runId, active]);

  if (!active && events.length === 0 && !error) return null;

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
              <details className="activity-disclosure">
                <summary className="activity-summary">
                  <span className="activity-marker" aria-hidden="true">{event.status === "success" ? "✓" : event.status === "failed" ? "!" : "·"}</span>
                  <span className="activity-copy">
                    <span className="activity-title-row"><strong>{event.title}</strong><span>{statusLabel(event.status)}</span></span>
                    <small>{new Date(event.occurred_at).toLocaleTimeString("zh-CN", { hour12: false })}{event.duration_ms !== null ? ` · ${event.duration_ms} ms` : ""}</small>
                  </span>
                </summary>
                <div className="activity-expanded">
                  <p>{event.summary}</p>
                  <span className="activity-details-label">{activityDetailsLabel(event)}</span>
                  {Object.keys(event.public_details).length > 0 && <span className="activity-details-values">{Object.entries(event.public_details).filter(([key]) => key !== "tool_call_id").map(([key, value]) => `${key}: ${value}`).join(" · ")}</span>}
                </div>
              </details>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
