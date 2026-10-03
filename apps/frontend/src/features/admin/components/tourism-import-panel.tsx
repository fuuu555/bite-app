"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  adminApi,
  type TourismImportRun,
  type TourismImportStart,
} from "@/features/admin/api/admin-api";
import {
  isTourismImportBatchComplete,
  latestTourismRunPerDataset,
  newTourismImportRuns,
  summarizeLatestTourismRuns,
  tourismImportDatasets,
} from "@/features/admin/utils/tourism-import-status";

const datasetLabels: Record<TourismImportRun["source_dataset"], string> = {
  food: "餐飲",
  attraction: "景點",
  hotel: "旅館民宿",
  service_site: "旅遊服務站",
};
const statusLabels: Record<TourismImportRun["status"], string> = {
  running: "匯入中",
  succeeded: "完成",
  failed: "失敗",
};
const summaryStatusLabels = {
  running: "匯入中",
  partial: "部分失敗",
  succeeded: "完成",
} as const;
const pollIntervalMs = 2000;
const resumeQuietPeriodMs = 10000;

type TrackingState =
  { mode: "batch"; baselineIds: Set<string> } | { mode: "resume"; startedAt: number };
type DialogState = "running" | "complete" | "partial" | "error";

async function getImportRuns(): Promise<TourismImportRun[]> {
  return adminApi<TourismImportRun[]>("/tourism/import-runs?limit=20");
}

export function TourismImportPanel({ onImportCompleted }: { onImportCompleted: () => void }) {
  const [runs, setRuns] = useState<TourismImportRun[]>([]);
  const [batchRuns, setBatchRuns] = useState<TourismImportRun[]>([]);
  const [tracking, setTracking] = useState(false);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(true);
  const [starting, setStarting] = useState(false);
  const [statusCheckFailed, setStatusCheckFailed] = useState(false);
  const [error, setError] = useState("");
  const trackingRef = useRef<TrackingState | null>(null);
  const resumeSawRunningRef = useRef(false);
  const resumeQuietSinceRef = useRef<number | null>(null);

  const refreshRuns = useCallback(async () => {
    const nextRuns = await getImportRuns();
    setRuns(nextRuns);
    return nextRuns;
  }, []);

  useEffect(() => {
    let active = true;
    void getImportRuns()
      .then((nextRuns) => {
        if (!active) return;
        setRuns(nextRuns);
        if (nextRuns.some((run) => run.status === "running")) {
          const earliestRunning = nextRuns
            .filter((run) => run.status === "running")
            .reduce((earliest, run) => Math.min(earliest, Date.parse(run.started_at)), Date.now());
          trackingRef.current = { mode: "resume", startedAt: earliestRunning };
          resumeSawRunningRef.current = true;
          setBatchRuns(nextRuns);
          setDialog("running");
          setDialogOpen(true);
          setTracking(true);
        }
      })
      .catch(() => {
        if (active) setError("無法載入觀光資料匯入紀錄。");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!dialogOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setDialogOpen(false);
      if (dialog === "complete" || dialog === "partial") setHistoryExpanded(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [dialog, dialogOpen]);

  useEffect(() => {
    if (!tracking) return;
    let active = true;

    async function pollRuns() {
      try {
        const nextRuns = await refreshRuns();
        if (!active) return;
        setStatusCheckFailed(false);
        const currentTracking = trackingRef.current;
        if (!currentTracking) return;

        if (currentTracking.mode === "batch") {
          const currentBatch = newTourismImportRuns(nextRuns, currentTracking.baselineIds);
          setBatchRuns(currentBatch);
          if (!isTourismImportBatchComplete(nextRuns, currentTracking.baselineIds)) return;
          finishImport(currentBatch);
          return;
        }

        const latestRuns = latestTourismRunPerDataset(nextRuns);
        const currentBatch = [...latestRuns.values()].filter(
          (run) => Date.parse(run.started_at) >= currentTracking.startedAt - 60_000,
        );
        setBatchRuns(currentBatch);
        const hasRunning = nextRuns.some((run) => run.status === "running");
        if (hasRunning) {
          resumeSawRunningRef.current = true;
          resumeQuietSinceRef.current = null;
          return;
        }
        if (!resumeSawRunningRef.current) return;
        resumeQuietSinceRef.current ??= Date.now();
        if (Date.now() - resumeQuietSinceRef.current < resumeQuietPeriodMs) return;
        finishImport(currentBatch);
      } catch {
        if (active) setStatusCheckFailed(true);
      }
    }

    function finishImport(finalRuns: TourismImportRun[]) {
      const hasFailures = finalRuns.some((run) => run.status === "failed");
      trackingRef.current = null;
      setTracking(false);
      setBatchRuns(finalRuns);
      setDialog(hasFailures ? "partial" : "complete");
      setDialogOpen(true);
      onImportCompleted();
    }

    const timer = window.setInterval(() => void pollRuns(), pollIntervalMs);
    void pollRuns();
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [onImportCompleted, refreshRuns, tracking]);

  const isRunning = useMemo(
    () => starting || tracking || runs.some((run) => run.status === "running"),
    [runs, starting, tracking],
  );
  const latestBatchRuns = useMemo(() => latestTourismRunPerDataset(batchRuns), [batchRuns]);
  const latestRunSummary = useMemo(() => summarizeLatestTourismRuns(runs), [runs]);
  const successfulCounts = useMemo(
    () =>
      batchRuns
        .filter((run) => run.status === "succeeded")
        .reduce(
          (counts, run) => ({
            inserted: counts.inserted + run.inserted_count,
            updated: counts.updated + run.updated_count,
            unchanged: counts.unchanged + run.unchanged_count,
          }),
          { inserted: 0, updated: 0, unchanged: 0 },
        ),
    [batchRuns],
  );

  async function startImport() {
    setStarting(true);
    setError("");
    setStatusCheckFailed(false);
    setBatchRuns([]);
    try {
      const baselineRuns = await refreshRuns();
      const result = await adminApi<TourismImportStart>("/tourism/import", { method: "POST" });
      const runningStartedAt = baselineRuns
        .filter((run) => run.status === "running")
        .map((run) => Date.parse(run.started_at));
      trackingRef.current =
        result.status === "already_running"
          ? {
              mode: "resume",
              startedAt: runningStartedAt.length ? Math.min(...runningStartedAt) : Date.now(),
            }
          : {
              mode: "batch",
              baselineIds: new Set(baselineRuns.map((run) => run.id)),
            };
      resumeSawRunningRef.current = result.status === "already_running";
      resumeQuietSinceRef.current = null;
      setDialog("running");
      setDialogOpen(true);
      setTracking(true);
    } catch {
      setError("無法開始觀光資料匯入，請稍後再試。");
      setDialog("error");
      setDialogOpen(true);
    } finally {
      setStarting(false);
    }
  }

  function closeImportDialog() {
    setDialogOpen(false);
    if (dialog === "complete" || dialog === "partial") setHistoryExpanded(false);
  }

  const dialogTitle =
    dialog === "complete"
      ? "觀光資料匯入完成"
      : dialog === "partial"
        ? "部分觀光資料匯入失敗"
        : dialog === "error"
          ? "無法開始匯入"
          : "正在匯入觀光署資料";

  return (
    <section className="admin-tourism-import" aria-labelledby="admin-tourism-import-title">
      <div>
        <p className="admin-section-kicker">官方資料</p>
        <h2 id="admin-tourism-import-title">觀光署資料整合</h2>
        <p>匯入後會直接顯示在地圖，並保留 BiteMap 店家資料與評分。</p>
      </div>
      <button
        type="button"
        className="button button--secondary"
        onClick={() => void startImport()}
        disabled={isRunning}
      >
        {isRunning ? "觀光資料匯入中…" : "一鍵匯入最新資料"}
      </button>
      {isRunning && !dialogOpen ? (
        <button
          type="button"
          className="button button--ghost"
          onClick={() => {
            setDialog("running");
            setDialogOpen(true);
          }}
        >
          查看匯入進度
        </button>
      ) : null}
      {error ? <p className="form-message is-error">{error}</p> : null}
      {runs.length ? (
        <>
          <div className="admin-tourism-import__history-bar">
            <div className="admin-tourism-import__summary" aria-live="polite">
              <span>
                最近匯入 {latestRunSummary.datasetCount} 類資料 ·{" "}
                {summaryStatusLabels[latestRunSummary.status]}
              </span>
              <small>
                新增 {latestRunSummary.inserted}／更新 {latestRunSummary.updated}／未變更{" "}
                {latestRunSummary.unchanged}
              </small>
            </div>
            <button
              type="button"
              className="button button--ghost admin-tourism-import__history-toggle"
              aria-controls="admin-tourism-import-runs"
              aria-expanded={historyExpanded}
              onClick={() => setHistoryExpanded((expanded) => !expanded)}
            >
              {historyExpanded ? "⌃ 收合紀錄" : "⌄ 展開紀錄"}
            </button>
          </div>
          {historyExpanded ? (
            <div
              id="admin-tourism-import-runs"
              className="admin-tourism-import__runs"
              aria-label="觀光資料匯入紀錄"
            >
              {runs.map((run) => (
                <div key={run.id}>
                  <span>
                    {datasetLabels[run.source_dataset]} · {statusLabels[run.status]}
                  </span>
                  <small>
                    {run.status === "succeeded"
                      ? `新增 ${run.inserted_count}／更新 ${run.updated_count}／未變更 ${run.unchanged_count}`
                      : run.error_message || new Date(run.started_at).toLocaleString("zh-TW")}
                  </small>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
      {dialog && dialogOpen ? (
        <div className="app-confirm-dialog__backdrop">
          <section
            className="app-confirm-dialog admin-tourism-import__dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="tourism-import-dialog-title"
            aria-describedby="tourism-import-dialog-message"
          >
            <h2 id="tourism-import-dialog-title">{dialogTitle}</h2>
            <div id="tourism-import-dialog-message" className="app-confirm-dialog__message">
              {dialog === "running" ? (
                <>
                  <p>
                    最近一次本機匯入約 13
                    秒；實際時間依網路與資料來源狀況而異。請稍候，完成後資料列表會自動更新。
                  </p>
                  {statusCheckFailed ? (
                    <p role="status">暫時無法取得進度，系統會繼續重試，不需要重新開始匯入。</p>
                  ) : null}
                  <div className="admin-tourism-import__dialog-runs" aria-live="polite">
                    {tourismImportDatasets.map((dataset) => {
                      const run = latestBatchRuns.get(dataset);
                      return (
                        <div key={dataset}>
                          <span>{datasetLabels[dataset]}</span>
                          <span>{run ? statusLabels[run.status] : "等待開始"}</span>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : dialog === "complete" ? (
                <p role="status">
                  新增 {successfulCounts.inserted}、更新 {successfulCounts.updated}、未變更{" "}
                  {successfulCounts.unchanged} 筆。資料列表已更新。
                </p>
              ) : dialog === "partial" ? (
                <>
                  <p role="alert">已完成的資料類型已匯入；請檢查失敗項目後再重試。</p>
                  <ul>
                    {batchRuns
                      .filter((run) => run.status === "failed")
                      .map((run) => (
                        <li key={run.id}>
                          {datasetLabels[run.source_dataset]}：{run.error_message || "匯入失敗"}
                        </li>
                      ))}
                  </ul>
                </>
              ) : (
                <p role="alert">{error}</p>
              )}
            </div>
            <div className="app-confirm-dialog__actions">
              <button
                type="button"
                className="button button--primary"
                onClick={closeImportDialog}
                autoFocus
              >
                {dialog === "running" ? "背景等待" : "關閉"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
