import { describe, expect, it } from "vitest";

import type { TourismImportRun } from "@/features/admin/api/admin-api";
import {
  isTourismImportBatchComplete,
  newTourismImportRuns,
  summarizeLatestTourismRuns,
} from "./tourism-import-status";

function run(
  id: string,
  source_dataset: TourismImportRun["source_dataset"],
  status: TourismImportRun["status"],
  started_at: string,
): TourismImportRun {
  return {
    id,
    source_dataset,
    source_url: "",
    status,
    started_at,
    completed_at: null,
    downloaded_count: 0,
    inserted_count: 0,
    updated_count: 0,
    unchanged_count: 0,
    invalid_count: 0,
    deactivated_count: 0,
    error_message: null,
  };
}

describe("tourism import status", () => {
  const baseline = new Set(["old-food"]);

  it("does not treat historical records as this import batch", () => {
    const runs = [
      run("old-food", "food", "succeeded", "2026-10-03T10:00:00Z"),
      run("old-attraction", "attraction", "succeeded", "2026-10-03T10:00:00Z"),
      run("old-hotel", "hotel", "succeeded", "2026-10-03T10:00:00Z"),
      run("old-service", "service_site", "succeeded", "2026-10-03T10:00:00Z"),
    ];

    expect(newTourismImportRuns(runs, baseline).map((item) => item.id)).toEqual([
      "old-attraction",
      "old-hotel",
      "old-service",
    ]);
    expect(isTourismImportBatchComplete(runs, baseline)).toBe(false);
  });

  it("waits until all four new datasets have terminal statuses", () => {
    const runs = [
      run("food", "food", "succeeded", "2026-10-03T10:01:00Z"),
      run("attraction", "attraction", "succeeded", "2026-10-03T10:02:00Z"),
      run("hotel", "hotel", "running", "2026-10-03T10:03:00Z"),
      run("service", "service_site", "succeeded", "2026-10-03T10:04:00Z"),
    ];
    expect(isTourismImportBatchComplete(runs, baseline)).toBe(false);
    expect(
      isTourismImportBatchComplete(
        [...runs, run("hotel-done", "hotel", "succeeded", "2026-10-03T10:03:01Z")],
        baseline,
      ),
    ).toBe(true);
  });

  it("treats a failed dataset as terminal so partial failures can be reported", () => {
    const runs = [
      run("food", "food", "succeeded", "2026-10-03T10:01:00Z"),
      run("attraction", "attraction", "failed", "2026-10-03T10:02:00Z"),
      run("hotel", "hotel", "succeeded", "2026-10-03T10:03:00Z"),
      run("service", "service_site", "succeeded", "2026-10-03T10:04:00Z"),
    ];
    expect(isTourismImportBatchComplete(runs, baseline)).toBe(true);
  });

  it("summarizes only the latest run for each dataset", () => {
    const runs = [
      { ...run("old-food", "food", "succeeded", "2026-10-03T10:00:00Z"), unchanged_count: 20 },
      { ...run("latest-food", "food", "succeeded", "2026-10-03T10:05:00Z"), inserted_count: 3 },
      {
        ...run("latest-attraction", "attraction", "succeeded", "2026-10-03T10:06:00Z"),
        updated_count: 4,
      },
    ];

    expect(summarizeLatestTourismRuns(runs)).toEqual({
      datasetCount: 2,
      status: "succeeded",
      inserted: 3,
      updated: 4,
      unchanged: 0,
    });
  });
});
