import { describe, expect, it } from "vitest";

import {
  createEmptyMealDraft,
  dateWithOffset,
  mealJoinDeadline,
  parseMealDraft,
  scheduledDateTime,
  weekendDates,
  withAutoMealTitle,
} from "./meal-draft";

describe("meal draft", () => {
  it("normalizes duplicate candidates and enforces the vote limit", () => {
    const restaurant = {
      id: "restaurant-1",
      name: "測試餐廳",
      address: "桃園市中壢區測試路 1 號",
      cuisine_name: "台灣料理",
      photo_url: null,
    };
    const parsed = parseMealDraft({
      ...createEmptyMealDraft(),
      candidates: [
        restaurant,
        restaurant,
        { ...restaurant, id: "2" },
        { ...restaurant, id: "3" },
        { ...restaurant, id: "4" },
      ],
    });

    expect(parsed?.candidates.map((candidate) => candidate.id)).toEqual(["restaurant-1", "2", "3"]);
  });

  it("auto names only untouched blank titles", () => {
    const restaurant = {
      id: "restaurant-1",
      name: "七號小店",
      address: "桃園市中壢區測試路 7 號",
      cuisine_name: null,
      photo_url: null,
    };
    const named = withAutoMealTitle({ ...createEmptyMealDraft(), candidates: [restaurant] });
    const manuallyCleared = withAutoMealTitle({ ...named, title: "", titleTouched: true });

    expect(named.title).toBe("一起吃 七號小店");
    expect(manuallyCleared.title).toBe("");
  });

  it("calculates a public join deadline from local date and time", () => {
    const draft = {
      ...createEmptyMealDraft(),
      scheduledDate: "2026-10-03",
      scheduledTime: "18:30",
      joinDeadlineMinutes: 15 as const,
    };

    expect(scheduledDateTime(draft)?.getHours()).toBe(18);
    expect(mealJoinDeadline(draft)?.getMinutes()).toBe(15);
  });

  it("offers deterministic relative and weekend dates", () => {
    const friday = new Date(2026, 9, 2, 8, 0);

    expect(dateWithOffset(1, friday)).toBe("2026-10-03");
    expect(weekendDates(friday)).toEqual({ saturday: "2026-10-03", sunday: "2026-10-04" });
  });
});
