import type { TourismImportRun } from "@/features/admin/api/admin-api";

export const tourismImportDatasets: TourismImportRun["source_dataset"][] = [
  "food",
  "attraction",
  "hotel",
  "service_site",
];

export function latestTourismRunPerDataset(
  runs: TourismImportRun[],
): Map<TourismImportRun["source_dataset"], TourismImportRun> {
  const latest = new Map<TourismImportRun["source_dataset"], TourismImportRun>();
  for (const run of runs) {
    const current = latest.get(run.source_dataset);
    if (!current || Date.parse(run.started_at) > Date.parse(current.started_at)) {
      latest.set(run.source_dataset, run);
    }
  }
  return latest;
}

export function newTourismImportRuns(
  runs: TourismImportRun[],
  baselineIds: Set<string>,
): TourismImportRun[] {
  return runs.filter((run) => !baselineIds.has(run.id));
}

export function isTourismImportBatchComplete(
  runs: TourismImportRun[],
  baselineIds: Set<string>,
): boolean {
  const latest = latestTourismRunPerDataset(newTourismImportRuns(runs, baselineIds));
  return tourismImportDatasets.every((dataset) => {
    const run = latest.get(dataset);
    return run !== undefined && run.status !== "running";
  });
}
