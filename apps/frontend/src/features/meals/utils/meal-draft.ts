"use client";

import { useSyncExternalStore } from "react";

import type {
  MealCreateInput,
  MealRestaurant,
  PrivateMealCondition,
  MealVisibility,
} from "@/features/meals/api/meals-api";

export const MEAL_DRAFT_STORAGE_KEY = "bitemap.mealDraft.v1";
export const MEAL_DEADLINE_OPTIONS = [5, 10, 15, 20, 30] as const;

export type MealDeadlineMinutes = (typeof MEAL_DEADLINE_OPTIONS)[number];
export type MealRestaurantMode = MealCreateInput["restaurant_mode"];
export type MealDraftRestaurant = Pick<
  MealRestaurant,
  "id" | "name" | "address" | "cuisine_name" | "photo_url"
>;

export type MealDraft = {
  version: 1;
  visibility: MealVisibility;
  privateCondition: PrivateMealCondition | null;
  title: string;
  titleTouched: boolean;
  description: string;
  scheduledDate: string;
  scheduledTime: string;
  joinDeadlineMinutes: MealDeadlineMinutes;
  capacity: number;
  restaurantMode: MealRestaurantMode;
  candidates: MealDraftRestaurant[];
};

const listeners = new Set<() => void>();
let cachedDraft: MealDraft | null | undefined;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDraftRestaurant(value: unknown): value is MealDraftRestaurant {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.address === "string" &&
    (typeof value.cuisine_name === "string" || value.cuisine_name === null) &&
    (typeof value.photo_url === "string" || value.photo_url === null)
  );
}

export function createEmptyMealDraft(): MealDraft {
  return {
    version: 1,
    visibility: "public",
    privateCondition: null,
    title: "",
    titleTouched: false,
    description: "",
    scheduledDate: "",
    scheduledTime: "",
    joinDeadlineMinutes: 15,
    capacity: 4,
    restaurantMode: "vote",
    candidates: [],
  };
}

export function parseMealDraft(value: unknown): MealDraft | null {
  if (!isRecord(value) || value.version !== 1) return null;
  if (value.visibility !== "public" && value.visibility !== "private") return null;
  const privateCondition = value.privateCondition === undefined ? null : value.privateCondition;
  if (
    privateCondition !== null &&
    privateCondition !== "male_only" &&
    privateCondition !== "female_only"
  ) {
    return null;
  }
  if (value.restaurantMode !== "direct" && value.restaurantMode !== "vote") return null;
  if (
    typeof value.title !== "string" ||
    typeof value.titleTouched !== "boolean" ||
    typeof value.description !== "string" ||
    typeof value.scheduledDate !== "string" ||
    typeof value.scheduledTime !== "string" ||
    typeof value.capacity !== "number" ||
    !MEAL_DEADLINE_OPTIONS.includes(value.joinDeadlineMinutes as MealDeadlineMinutes) ||
    !Array.isArray(value.candidates)
  ) {
    return null;
  }

  const uniqueCandidates = value.candidates
    .filter(isDraftRestaurant)
    .filter((candidate, index, candidates) => {
      return candidates.findIndex((item) => item.id === candidate.id) === index;
    })
    .slice(0, value.restaurantMode === "direct" ? 1 : 3);

  return {
    version: 1,
    visibility: value.visibility,
    privateCondition,
    title: value.title.slice(0, 120),
    titleTouched: value.titleTouched,
    description: value.description.slice(0, 500),
    scheduledDate: value.scheduledDate,
    scheduledTime: value.scheduledTime,
    joinDeadlineMinutes: value.joinDeadlineMinutes as MealDeadlineMinutes,
    capacity: Math.max(2, Math.min(20, Math.round(value.capacity))),
    restaurantMode: value.restaurantMode,
    candidates: uniqueCandidates,
  };
}

function readStoredDraft() {
  if (cachedDraft !== undefined) return cachedDraft;
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(MEAL_DRAFT_STORAGE_KEY);
    cachedDraft = raw ? parseMealDraft(JSON.parse(raw)) : null;
  } catch {
    cachedDraft = null;
  }
  return cachedDraft;
}

function emitDraftChange() {
  listeners.forEach((listener) => listener());
}

export function saveMealDraft(draft: MealDraft): boolean {
  const nextDraft = parseMealDraft(draft);
  if (!nextDraft) return false;
  cachedDraft = nextDraft;
  let persisted = true;
  try {
    window.sessionStorage.setItem(MEAL_DRAFT_STORAGE_KEY, JSON.stringify(nextDraft));
  } catch {
    persisted = false;
  }
  emitDraftChange();
  return persisted;
}

export function clearMealDraft() {
  cachedDraft = null;
  try {
    window.sessionStorage.removeItem(MEAL_DRAFT_STORAGE_KEY);
  } catch {
    // In-memory state still clears when storage is unavailable.
    // 儲存空間不可用時，仍要清除目前頁籤中的記憶體草稿。
  }
  emitDraftChange();
}

export function updateMealDraft(
  updater: (draft: MealDraft) => MealDraft,
  fallback = createEmptyMealDraft(),
) {
  const current = readStoredDraft() ?? fallback;
  const next = updater(current);
  return saveMealDraft(next);
}

export function addRestaurantToMealDraft(
  restaurant: MealDraftRestaurant,
  preferredMode?: MealRestaurantMode,
) {
  const current = readStoredDraft() ?? createEmptyMealDraft();
  const mode = preferredMode ?? current.restaurantMode;
  const draft = { ...current, restaurantMode: mode };
  const existing = draft.candidates.some((candidate) => candidate.id === restaurant.id);
  const outcome: "added" | "replaced" | "exists" | "full" = existing
    ? "exists"
    : mode === "vote" && draft.candidates.length >= 3
      ? "full"
      : mode === "direct" && draft.candidates.length > 0
        ? "replaced"
        : "added";
  const nextDraft =
    outcome === "exists" || outcome === "full"
      ? draft
      : withAutoMealTitle({
          ...draft,
          candidates: mode === "direct" ? [restaurant] : [...draft.candidates, restaurant],
        });
  const persisted = saveMealDraft(nextDraft);
  return { outcome, persisted };
}

export function removeRestaurantFromMealDraft(restaurantId: string) {
  return updateMealDraft((draft) => ({
    ...draft,
    candidates: draft.candidates.filter((candidate) => candidate.id !== restaurantId),
  }));
}

export function withAutoMealTitle(draft: MealDraft): MealDraft {
  if (draft.titleTouched || draft.title.trim() || !draft.candidates.length) return draft;
  return { ...draft, title: `一起吃 ${draft.candidates[0].name}` };
}

export function getMealDraftSnapshot() {
  return readStoredDraft();
}

export function subscribeMealDraft(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useMealDraft() {
  return useSyncExternalStore(subscribeMealDraft, getMealDraftSnapshot, () => null);
}

export function localDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function dateWithOffset(days: number, now = new Date()) {
  const date = new Date(now);
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + days);
  return localDateValue(date);
}

export function weekendDates(now = new Date()) {
  const day = now.getDay();
  const daysUntilSaturday = (6 - day + 7) % 7;
  const saturdayOffset = daysUntilSaturday === 0 ? 0 : daysUntilSaturday;
  return {
    saturday: dateWithOffset(saturdayOffset, now),
    sunday: dateWithOffset(saturdayOffset + 1, now),
  };
}

export function scheduledDateTime(draft: MealDraft) {
  if (!draft.scheduledDate || !draft.scheduledTime) return null;
  const date = new Date(`${draft.scheduledDate}T${draft.scheduledTime}`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function mealJoinDeadline(draft: MealDraft) {
  const scheduled = scheduledDateTime(draft);
  if (!scheduled || draft.visibility !== "public") return null;
  return new Date(scheduled.getTime() - draft.joinDeadlineMinutes * 60_000);
}
