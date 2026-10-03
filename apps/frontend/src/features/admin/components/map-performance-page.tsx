"use client";

import { useCallback, useEffect, useState } from "react";

import {
  adminApi,
  type MapPerformanceMetrics,
  type MapQueryMetric,
} from "@/features/admin/api/admin-api";

const refreshIntervalMs = 5000;

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("zh-TW", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function statusLabel(status: MapPerformanceMetrics["status"]) {
  return status === "critical" ? "嚴重" : status === "attention" ? "需要注意" : "正常";
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="monitoring-metric-card">
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function QueryStatus({ query }: { query: MapQueryMetric }) {
  const label = query.response_status === "zoom_required"
    ? "需放大"
    : query.response_status === "error"
      ? "錯誤"
      : "完成";
  return <span className={`monitoring-status monitoring-status--${query.response_status}`}>{label}</span>;
}

export function MapPerformancePage() {
  const [metrics, setMetrics] = useState<MapPerformanceMetrics | null>(null);
  const [error, setError] = useState("");

  const loadMetrics = useCallback(async () => {
    try {
      const next = await adminApi<MapPerformanceMetrics>("/monitoring/map");
      setMetrics(next);
      setError("");
    } catch {
      setError("監控資料暫時無法更新，請確認後端服務。 ");
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadMetrics(), 0);
    const timer = window.setInterval(() => void loadMetrics(), refreshIntervalMs);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(timer);
    };
  }, [loadMetrics]);

  return (
    <main className="admin-page monitoring-page">
      <header className="admin-page__header">
        <div>
          <p className="monitoring-eyebrow">BiteMap / Operations</p>
          <h1>系統監控</h1>
          <p>即時觀察地圖查詢效能，並依實際數字判斷是否需要升級架構。</p>
        </div>
        {metrics ? (
          <div className={`monitoring-health monitoring-health--${metrics.status}`}>
            <span className="monitoring-health__dot" aria-hidden="true" />
            {statusLabel(metrics.status)}
          </div>
        ) : null}
      </header>

      {error ? <p className="monitoring-feedback is-error" role="alert">{error}</p> : null}
      {!metrics ? (
        <div className="monitoring-empty" aria-busy="true">正在載入地圖效能資料…</div>
      ) : (
        <>
          <section className="monitoring-summary" aria-label="地圖效能摘要">
            <MetricCard label="最近 5 分鐘查詢" value={`${metrics.query_count} 次`} note={`已發布店家 ${metrics.published_restaurant_count} 筆`} />
            <MetricCard label="P95 查詢時間" value={`${metrics.p95_duration_ms} ms`} note={`平均 ${metrics.average_duration_ms} ms`} />
            <MetricCard label="快取命中率" value={formatPercent(metrics.cache_hit_rate)} note={`${metrics.cache_hits} 命中／${metrics.cache_misses} 未命中`} />
            <MetricCard label="需要放大比例" value={formatPercent(metrics.zoom_required_rate)} note={`${metrics.zoom_required_count} 次 zoom_required`} />
            <MetricCard label="錯誤率" value={formatPercent(metrics.error_rate)} note={`${metrics.error_count} 次錯誤`} />
          </section>

          <section className="monitoring-panel" aria-labelledby="monitoring-alerts-title">
            <div className="monitoring-panel__heading">
              <div>
                <p className="monitoring-eyebrow">Upgrade signals</p>
                <h2 id="monitoring-alerts-title">升級建議</h2>
              </div>
              <small>每 5 秒更新 · 連續 3 個窗口且每窗口至少 10 次查詢才提醒 · 最近更新 {formatTime(metrics.last_updated_at)}</small>
            </div>
            {metrics.alerts.length ? (
              <ul className="monitoring-alerts">
                {metrics.alerts.map((alert) => <li key={alert}>{alert}</li>)}
              </ul>
            ) : (
              <p className="monitoring-ok">目前沒有達到升級門檻，維持現有地圖查詢架構即可。</p>
            )}
            <div className="monitoring-thresholds">
              <span>後端群聚：zoom_required &gt; 5%</span>
              <span>向量圖磚：已發布店家 &gt; 5,000</span>
              <span>Redis：多 instance 或命中率長期 &lt; 40%</span>
            </div>
          </section>

          <section className="monitoring-panel" aria-labelledby="monitoring-queries-title">
            <div className="monitoring-panel__heading">
              <div>
                <p className="monitoring-eyebrow">Live query stream</p>
                <h2 id="monitoring-queries-title">最近查詢</h2>
              </div>
              <span className="monitoring-cache-count">目前快取 {metrics.cache_entries} 筆</span>
            </div>
            {metrics.recent_queries.length ? (
              <div className="monitoring-table-wrap">
                <table className="monitoring-table">
                  <thead>
                    <tr><th>時間</th><th>查詢摘要</th><th>耗時</th><th>結果</th><th>快取</th><th>狀態</th></tr>
                  </thead>
                  <tbody>
                    {metrics.recent_queries.map((query) => (
                      <tr key={`${query.occurred_at}-${query.duration_ms}-${query.query_summary}`}>
                        <td>{formatTime(query.occurred_at)}</td>
                        <td>{query.query_summary}</td>
                        <td>{query.duration_ms} ms</td>
                        <td>{query.result_count}</td>
                        <td>{query.cache_hit ? "命中" : "未命中"}</td>
                        <td><QueryStatus query={query} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="monitoring-ok">尚未收到地圖查詢。</p>
            )}
          </section>
        </>
      )}
    </main>
  );
}
