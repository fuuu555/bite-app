"use client";

import {
  IconArrowRight,
  IconCalendarEvent,
  IconClock,
  IconMapSearch,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AppConfirmDialog } from "@/shared/ui/app-confirm-dialog";
import { fetchExploreRestaurant } from "@/features/home/api/explore-api";
import {
  addRestaurantToMealDraft,
  clearMealDraft,
  createEmptyMealDraft,
  dateWithOffset,
  MEAL_DEADLINE_OPTIONS,
  mealJoinDeadline,
  removeRestaurantFromMealDraft,
  saveMealDraft,
  scheduledDateTime,
  updateMealDraft,
  useMealDraft,
  weekendDates,
  withAutoMealTitle,
  type MealDeadlineMinutes,
} from "@/features/meals/utils/meal-draft";
import {
  addMealCandidate,
  createMeal,
  type Meal,
  MealsApiError,
} from "@/features/meals/api/meals-api";

const timeOptions = [
  { label: "午餐", value: "12:00" },
  { label: "下午茶", value: "15:00" },
  { label: "晚餐", value: "18:30" },
  { label: "宵夜", value: "21:00" },
] as const;

function actionError(error: unknown) {
  if (error instanceof MealsApiError && typeof error.detail === "string") return error.detail;
  return "這個操作暫時無法完成，請再試一次。";
}

function formatDeadline(value: Date | null) {
  if (!value) return "選好日期與時間後顯示";
  return new Intl.DateTimeFormat("zh-TW", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(value);
}

export function MealCreateDialog({
  initialRestaurantId,
  onClose,
  onCreated,
}: {
  initialRestaurantId?: string;
  onClose: () => void;
  onCreated: (meal: Meal) => void;
}) {
  const draft = useMealDraft();
  const loadedRestaurantId = useRef<string | null>(null);
  const [error, setError] = useState("");
  const [storageWarning, setStorageWarning] = useState("");
  const [busy, setBusy] = useState(false);
  const [openedAt] = useState(() => Date.now());
  const [weekendOpen, setWeekendOpen] = useState(false);
  const [customDateOpen, setCustomDateOpen] = useState(false);
  const [customTimeOpen, setCustomTimeOpen] = useState(false);
  const [abandonConfirmOpen, setAbandonConfirmOpen] = useState(false);

  useEffect(() => {
    if (!draft) saveMealDraft(createEmptyMealDraft());
  }, [draft]);

  useEffect(() => {
    if (!initialRestaurantId || loadedRestaurantId.current === initialRestaurantId) return;
    loadedRestaurantId.current = initialRestaurantId;
    fetchExploreRestaurant(initialRestaurantId)
      .then((restaurant) => {
        const result = addRestaurantToMealDraft({
          id: restaurant.id,
          name: restaurant.name,
          address: restaurant.address,
          cuisine_name: restaurant.primary_cuisine.display_name,
          photo_url: restaurant.photo_url,
        });
        if (!result.persisted) setStorageWarning("瀏覽器無法保存草稿，請在離開此頁前完成建立。");
      })
      .catch(() => setError("這家餐廳暫時無法加入草稿，請返回餐廳頁再試一次。"));
  }, [initialRestaurantId]);

  if (!draft) return null;

  const today = dateWithOffset(0);
  const tomorrow = dateWithOffset(1);
  const weekend = weekendDates();
  const selectedScheduledAt = scheduledDateTime(draft);
  const selectedDeadline = mealJoinDeadline(draft);
  const selectedQuickTime = timeOptions.some((option) => option.value === draft.scheduledTime);

  const update = (updater: Parameters<typeof updateMealDraft>[0]) => {
    if (!updateMealDraft(updater, draft)) {
      setStorageWarning("瀏覽器無法保存草稿，請在離開此頁前完成建立。");
    }
  };

  const chooseDate = (value: string) => {
    update((current) => {
      const selected = current.scheduledTime ? new Date(`${value}T${current.scheduledTime}`) : null;
      return {
        ...current,
        scheduledDate: value,
        scheduledTime: selected && selected.getTime() <= Date.now() ? "" : current.scheduledTime,
      };
    });
    setCustomDateOpen(false);
  };

  const timeIsPast = (value: string) => {
    if (!draft.scheduledDate) return false;
    return new Date(`${draft.scheduledDate}T${value}`).getTime() <= openedAt;
  };

  const abandon = () => {
    setAbandonConfirmOpen(true);
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    const scheduled = scheduledDateTime(draft);
    const deadline = mealJoinDeadline(draft);
    if (!draft.title.trim()) {
      setError("請填寫飯局名稱。也可以先選餐廳，系統會幫你帶入名稱。");
      return;
    }
    if (!scheduled) {
      setError("請選擇用餐日期與時間。");
      return;
    }
    if (scheduled.getTime() <= Date.now()) {
      setError("用餐時間必須晚於現在，請重新選擇。");
      return;
    }
    if (draft.visibility === "public" && (!deadline || deadline.getTime() <= Date.now())) {
      setError("加入截止時間已經過了，請把用餐時間往後調整。");
      return;
    }
    if (!draft.candidates.length) {
      setError("請先到餐廳詳細頁選擇至少一家店。草稿會保留，不用重新填寫。");
      return;
    }

    setBusy(true);
    try {
      let meal = await createMeal({
        visibility: draft.visibility,
        private_condition: draft.visibility === "private" ? draft.privateCondition : null,
        title: draft.title.trim(),
        description: draft.description.trim() || null,
        scheduled_at: scheduled.toISOString(),
        join_deadline: draft.visibility === "public" ? (deadline?.toISOString() ?? null) : null,
        capacity: draft.capacity,
        restaurant_mode: draft.restaurantMode,
        restaurant_id: draft.candidates[0]?.id ?? null,
      });
      // Candidate one is created together with the meal; append the remaining draft choices in order.
      // 第一家候選隨飯局建立，其餘候選依草稿順序透過既有權限端點補上。
      if (draft.restaurantMode === "vote") {
        for (const candidate of draft.candidates.slice(1)) {
          meal = await addMealCandidate(meal.id, candidate.id);
        }
      }
      clearMealDraft();
      onCreated(meal);
    } catch (caught) {
      setError(actionError(caught));
    } finally {
      setBusy(false);
    }
  };

  const dateIsWeekend =
    draft.scheduledDate === weekend.saturday || draft.scheduledDate === weekend.sunday;

  return (
    <>
      <dialog className="meal-create-dialog" open aria-labelledby="meal-create-title">
        <button className="meal-create-dialog__backdrop" type="button" onClick={onClose}>
          <span>關閉建立約飯</span>
        </button>
        <section className="meal-create-sheet">
          <header>
            <div>
              <h1 id="meal-create-title">揪一餐，認識同樣愛吃的人</h1>
              <p>內容會保留在這個分頁，可以放心出去選店。</p>
            </div>
            <button type="button" onClick={onClose} aria-label="關閉建立約飯">
              <IconX aria-hidden="true" />
            </button>
          </header>
          <form onSubmit={submit}>
            <fieldset className="meal-choice-group">
              <legend>加入方式</legend>
              <label className={draft.visibility === "public" ? "is-selected" : ""}>
                <input
                  type="radio"
                  name="visibility"
                  checked={draft.visibility === "public"}
                  onChange={() =>
                    update((current) => ({
                      ...current,
                      visibility: "public",
                      privateCondition: null,
                    }))
                  }
                />
                <span>
                  <strong>公開加入</strong>
                  <small>額滿前可直接加入</small>
                </span>
              </label>
              <label className={draft.visibility === "private" ? "is-selected" : ""}>
                <input
                  type="radio"
                  name="visibility"
                  checked={draft.visibility === "private"}
                  onChange={() =>
                    update((current) =>
                      withAutoMealTitle({
                        ...current,
                        visibility: "private",
                        restaurantMode: "direct",
                        candidates: current.candidates.slice(0, 1),
                      }),
                    )
                  }
                />
                <span>
                  <strong>私人約飯</strong>
                  <small>由你決定是否接受申請</small>
                </span>
              </label>
            </fieldset>

            {draft.visibility === "private" ? (
              <fieldset className="meal-choice-group">
                <legend>申請條件</legend>
                <p className="meal-condition-note">
                  只作為飯局標示，不會自動驗證或攔截申請，由你自行審核。
                </p>
                <label className={draft.privateCondition === null ? "is-selected" : ""}>
                  <input
                    type="radio"
                    name="private-condition"
                    checked={draft.privateCondition === null}
                    onChange={() => update((current) => ({ ...current, privateCondition: null }))}
                  />
                  <span>
                    <strong>不限</strong>
                    <small>依申請審核決定</small>
                  </span>
                </label>
                <label className={draft.privateCondition === "male_only" ? "is-selected" : ""}>
                  <input
                    type="radio"
                    name="private-condition"
                    checked={draft.privateCondition === "male_only"}
                    onChange={() =>
                      update((current) => ({ ...current, privateCondition: "male_only" }))
                    }
                  />
                  <span>
                    <strong>限男性</strong>
                    <small>由發起人自行審核</small>
                  </span>
                </label>
                <label className={draft.privateCondition === "female_only" ? "is-selected" : ""}>
                  <input
                    type="radio"
                    name="private-condition"
                    checked={draft.privateCondition === "female_only"}
                    onChange={() =>
                      update((current) => ({ ...current, privateCondition: "female_only" }))
                    }
                  />
                  <span>
                    <strong>限女性</strong>
                    <small>由發起人自行審核</small>
                  </span>
                </label>
              </fieldset>
            ) : null}

            <label>
              飯局名稱
              <input
                required
                maxLength={120}
                value={draft.title}
                onChange={(event) =>
                  update((current) => ({
                    ...current,
                    title: event.target.value,
                    titleTouched: true,
                  }))
                }
                placeholder="選一家店後可自動帶入"
              />
            </label>
            <label>
              簡介<span>選填</span>
              <textarea
                maxLength={500}
                value={draft.description}
                onChange={(event) =>
                  update((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="想吃什麼、想認識怎樣的飯友？"
              />
            </label>

            <fieldset className="meal-time-picker">
              <legend>用餐時間</legend>
              <div className="meal-time-picker__group">
                <span>
                  <IconCalendarEvent aria-hidden="true" /> 日期
                </span>
                <div className="meal-time-chips">
                  <button
                    type="button"
                    className={draft.scheduledDate === today ? "is-selected" : ""}
                    onClick={() => chooseDate(today)}
                  >
                    今天
                  </button>
                  <button
                    type="button"
                    className={draft.scheduledDate === tomorrow ? "is-selected" : ""}
                    onClick={() => chooseDate(tomorrow)}
                  >
                    明天
                  </button>
                  <button
                    type="button"
                    className={dateIsWeekend ? "is-selected" : ""}
                    onClick={() => setWeekendOpen((open) => !open)}
                  >
                    本週末
                  </button>
                  <button
                    type="button"
                    className={customDateOpen ? "is-selected" : ""}
                    onClick={() => setCustomDateOpen((open) => !open)}
                  >
                    自訂
                  </button>
                </div>
                {weekendOpen ? (
                  <div className="meal-time-subchips">
                    <button
                      type="button"
                      className={draft.scheduledDate === weekend.saturday ? "is-selected" : ""}
                      onClick={() => chooseDate(weekend.saturday)}
                    >
                      週六
                    </button>
                    <button
                      type="button"
                      className={draft.scheduledDate === weekend.sunday ? "is-selected" : ""}
                      onClick={() => chooseDate(weekend.sunday)}
                    >
                      週日
                    </button>
                  </div>
                ) : null}
                {customDateOpen ? (
                  <input
                    type="date"
                    min={today}
                    value={draft.scheduledDate}
                    onChange={(event) => chooseDate(event.target.value)}
                  />
                ) : null}
              </div>
              <div className="meal-time-picker__group">
                <span>
                  <IconClock aria-hidden="true" /> 時間
                </span>
                <div className="meal-time-chips">
                  {timeOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={draft.scheduledTime === option.value ? "is-selected" : ""}
                      disabled={timeIsPast(option.value)}
                      onClick={() => {
                        update((current) => ({ ...current, scheduledTime: option.value }));
                        setCustomTimeOpen(false);
                      }}
                    >
                      {option.label}
                      <small>{option.value}</small>
                    </button>
                  ))}
                  <button
                    type="button"
                    className={
                      customTimeOpen || (draft.scheduledTime && !selectedQuickTime)
                        ? "is-selected"
                        : ""
                    }
                    onClick={() => setCustomTimeOpen((open) => !open)}
                  >
                    自訂
                  </button>
                </div>
                {customTimeOpen ? (
                  <input
                    type="time"
                    value={draft.scheduledTime}
                    onChange={(event) =>
                      update((current) => ({ ...current, scheduledTime: event.target.value }))
                    }
                  />
                ) : null}
                {selectedScheduledAt ? (
                  <strong className="meal-time-summary">
                    預定{" "}
                    {new Intl.DateTimeFormat("zh-TW", {
                      month: "numeric",
                      day: "numeric",
                      weekday: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(selectedScheduledAt)}
                  </strong>
                ) : null}
              </div>
            </fieldset>

            <div className="meal-create-fields">
              <label>
                人數上限
                <input
                  required
                  type="number"
                  min="2"
                  max="20"
                  value={draft.capacity}
                  onChange={(event) =>
                    update((current) => ({ ...current, capacity: Number(event.target.value) }))
                  }
                />
              </label>
            </div>

            <fieldset className="meal-choice-group">
              <legend>選餐廳方式</legend>
              <label className={draft.restaurantMode === "direct" ? "is-selected" : ""}>
                <input
                  type="radio"
                  name="restaurant-mode"
                  checked={draft.restaurantMode === "direct"}
                  onChange={() =>
                    update((current) => ({
                      ...current,
                      restaurantMode: "direct",
                      candidates: current.candidates.slice(0, 1),
                    }))
                  }
                />
                <span>
                  <strong>先決定餐廳</strong>
                  <small>建立時直接選定</small>
                </span>
              </label>
              <label className={draft.restaurantMode === "vote" ? "is-selected" : ""}>
                <input
                  type="radio"
                  name="restaurant-mode"
                  checked={draft.restaurantMode === "vote"}
                  onChange={() => update((current) => ({ ...current, restaurantMode: "vote" }))}
                />
                <span>
                  <strong>集合後投票</strong>
                  <small>
                    {draft.visibility === "private"
                      ? "審核通過後由正式成員投票"
                      : "公開約飯最多三家候選"}
                  </small>
                </span>
              </label>
            </fieldset>

            {draft.visibility === "public" ? (
              <fieldset className="meal-deadline-control">
                <legend>加入截止時間</legend>
                <div className="meal-deadline-chips">
                  {MEAL_DEADLINE_OPTIONS.map((minutes) => (
                    <button
                      key={minutes}
                      type="button"
                      className={draft.joinDeadlineMinutes === minutes ? "is-selected" : ""}
                      onClick={() =>
                        update((current) => ({
                          ...current,
                          joinDeadlineMinutes: minutes as MealDeadlineMinutes,
                        }))
                      }
                    >
                      {minutes} 分
                    </button>
                  ))}
                </div>
                <p>
                  用餐前關閉加入 · <strong>{formatDeadline(selectedDeadline)}</strong>
                </p>
              </fieldset>
            ) : null}

            <section className="meal-restaurant-picker">
              <header>
                <div>
                  <h2>{draft.restaurantMode === "direct" ? "選定餐廳" : "候選餐廳"}</h2>
                  <p>
                    {draft.restaurantMode === "direct"
                      ? "從餐廳詳細頁選一家店"
                      : `已選 ${draft.candidates.length} / 3 家，飯友加入後才可看票數`}
                  </p>
                </div>
                <Link href="/" className="meal-picker-explore">
                  <IconMapSearch aria-hidden="true" />
                  {draft.candidates.length ? "繼續選店" : "前往選店"}
                </Link>
              </header>
              {draft.candidates.length ? (
                <div className="meal-selected-candidates">
                  {draft.candidates.map((candidate, index) => (
                    <div className="meal-selected-restaurant" key={candidate.id}>
                      <b>{draft.restaurantMode === "vote" ? `候選 ${index + 1}` : "餐廳"}</b>
                      <span>
                        <strong>{candidate.name}</strong>
                        <small>{candidate.cuisine_name || "餐廳"}</small>
                      </span>
                      <button
                        type="button"
                        onClick={() => removeRestaurantFromMealDraft(candidate.id)}
                        aria-label={`移除 ${candidate.name}`}
                      >
                        <IconX aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="meal-picker-empty">尚未選店。草稿會保留，請到餐廳詳細頁加入。</p>
              )}
            </section>

            {storageWarning ? (
              <p className="meal-form-warning" role="status">
                {storageWarning}
              </p>
            ) : null}
            {error ? (
              <p className="meal-form-error" role="alert">
                {error}
              </p>
            ) : null}
            <footer>
              <button type="button" className="meal-abandon-button" onClick={abandon}>
                <IconTrash aria-hidden="true" />
                放棄草稿
              </button>
              <button type="button" onClick={onClose}>
                稍後再填
              </button>
              <button type="submit" className="button button--primary" disabled={busy}>
                {busy ? "建立中…" : "建立約飯"}
                <IconArrowRight aria-hidden="true" />
              </button>
            </footer>
          </form>
        </section>
      </dialog>
      <AppConfirmDialog
        open={abandonConfirmOpen}
        title="放棄約飯草稿"
        message="已填內容與候選餐廳都會清除，確定要放棄嗎？"
        confirmLabel="放棄草稿"
        danger
        onCancel={() => setAbandonConfirmOpen(false)}
        onConfirm={() => {
          clearMealDraft();
          setAbandonConfirmOpen(false);
          onClose();
        }}
      />
    </>
  );
}
