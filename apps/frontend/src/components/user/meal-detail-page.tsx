"use client";

import {
  IconArrowLeft,
  IconCalendarEvent,
  IconCheck,
  IconMapPin,
  IconUserMinus,
  IconUsers,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { MealDetail } from "@/components/user/meals-page";
import {
  cancelMeal,
  departedMealMembers,
  fetchMeal,
  joinMeal,
  leaveMeal,
  removeMealMember,
  type Meal,
  MealsApiError,
} from "@/lib/meals-api";

function formatMealTime(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusLabel(meal: Meal) {
  if (meal.status === "awaiting_host_decision") return "等待發起人確認";
  if (meal.status === "voting") return "投票中";
  if (meal.status === "decided") return "已成團";
  if (meal.member_count >= meal.capacity) return "已額滿";
  return meal.visibility === "private" ? "私人約飯" : "可加入";
}

function actionError(error: unknown) {
  if (error instanceof MealsApiError && typeof error.detail === "string") return error.detail;
  return "這個操作暫時無法完成，請再試一次。";
}

export function MealDetailPage({ mealId }: { mealId: string }) {
  const router = useRouter();
  const [meal, setMeal] = useState<Meal | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [liveNotice, setLiveNotice] = useState("");
  const previousMealRef = useRef<Meal | null>(null);

  useEffect(() => {
    if (!liveNotice) return;
    const timer = window.setTimeout(() => setLiveNotice(""), 2_000);
    return () => window.clearTimeout(timer);
  }, [liveNotice]);

  useEffect(() => {
    const controller = new AbortController();
    let refreshing = false;
    let loadedOnce = false;
    const refresh = async () => {
      if (refreshing || controller.signal.aborted) return;
      refreshing = true;
      try {
        const nextMeal = await fetchMeal(mealId, controller.signal);
        if (controller.signal.aborted) return;
        const previousMeal = previousMealRef.current;
        if (previousMeal) {
          const departed = departedMealMembers(previousMeal, nextMeal);
          if (departed.length === 1) {
            setLiveNotice(`${departed[0].display_name} 已離開約飯。`);
          } else if (departed.length > 1) {
            setLiveNotice(`${departed[0].display_name} 等 ${departed.length} 位成員已離開約飯。`);
          }
        }
        previousMealRef.current = nextMeal;
        loadedOnce = true;
        setMeal(nextMeal);
        setState("ready");
      } catch (caught) {
        if (controller.signal.aborted) return;
        if (caught instanceof MealsApiError && caught.status === 410) {
          controller.abort();
          router.replace("/meals?cancelled=host");
          return;
        }
        // Keep the last valid meal during a transient polling failure.
        // 背景更新短暫失敗時保留最後一次有效資料，不讓整頁突然切成錯誤畫面。
        if (!loadedOnce) {
          setError(actionError(caught));
          setState("error");
        }
      } finally {
        refreshing = false;
      }
    };
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    const refreshOnFocus = () => void refresh();

    void refresh();
    const timer = window.setInterval(() => void refresh(), 3_000);
    window.addEventListener("focus", refreshOnFocus);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshOnFocus);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [mealId, router]);

  const updateMeal = (nextMeal: Meal) => {
    if (nextMeal.status === "cancelled") {
      router.replace("/meals?cancelled=1");
      return;
    }
    const previousMeal = previousMealRef.current;
    if (previousMeal) {
      const departed = departedMealMembers(previousMeal, nextMeal);
      if (departed.length === 1) setLiveNotice(`${departed[0].display_name} 已離開約飯。`);
    }
    previousMealRef.current = nextMeal;
    setMeal(nextMeal);
  };

  const act = async (operation: () => Promise<Meal>) => {
    setBusy(true);
    setError("");
    try {
      updateMeal(await operation());
    } catch (caught) {
      setError(actionError(caught));
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") {
    return <main className="meal-detail-page meal-detail-page--state">正在載入飯局…</main>;
  }

  if (state === "error" || !meal) {
    return (
      <main className="meal-detail-page meal-detail-page--state">
        <h1>飯局暫時無法載入</h1>
        <p>{error || "這場飯局可能已解除或不存在。"}</p>
        <Link className="button button--primary" href="/meals">
          返回約飯列表
        </Link>
      </main>
    );
  }

  // A ballot has multiple equal candidates, so the header must not imply candidate 1 is chosen.
  // 投票中的候選店家地位相同，頁首不可只突出第一家造成已選定的誤解。
  const restaurant =
    meal.decided_restaurant ??
    (meal.candidates.length === 1 ? meal.candidates[0].restaurant : null);
  const canLeave =
    !meal.can_manage &&
    (meal.my_membership_status === "member" || meal.my_membership_status === "pending");
  const canCancel =
    meal.can_manage &&
    ["open", "awaiting_host_decision", "voting", "decided"].includes(meal.status);

  return (
    <main className="meal-detail-page">
      <Link className="meal-detail-page__back" href="/meals">
        <IconArrowLeft aria-hidden="true" /> 返回約飯列表
      </Link>
      {liveNotice ? (
        <p className="meal-feedback is-success" role="status">
          <IconUserMinus aria-hidden="true" />
          {liveNotice}
        </p>
      ) : null}
      <article className="meal-detail-page__surface">
        <header className="meal-detail-page__header">
          <div className="meal-detail-page__topline">
            <span className={`meal-status is-${meal.status}`}>{statusLabel(meal)}</span>
            <span>{meal.visibility === "private" ? "私人約飯" : "公開加入"}</span>
          </div>
          <p>{meal.host.display_name} 發起</p>
          <h1>{meal.title}</h1>
          {meal.description ? (
            <p className="meal-detail-page__description">{meal.description}</p>
          ) : null}
          <dl>
            <div>
              <dt>
                <IconCalendarEvent aria-hidden="true" />
              </dt>
              <dd>{formatMealTime(meal.scheduled_at)}</dd>
            </div>
            <div>
              <dt>
                <IconUsers aria-hidden="true" />
              </dt>
              <dd>
                {meal.member_count} / {meal.capacity} 人
              </dd>
            </div>
          </dl>
          {restaurant ? (
            <Link className="meal-detail-page__restaurant" href={`/restaurants/${restaurant.id}`}>
              <span>
                <strong>{restaurant.name}</strong>
                <small>
                  <IconMapPin aria-hidden="true" />
                  {restaurant.address}
                </small>
              </span>
              <span>查看餐廳</span>
            </Link>
          ) : null}
        </header>

        <MealDetail meal={meal} onChange={updateMeal} onError={setError} />

        <details className="meal-detail-page__members">
          <summary>
            <span>成員</span>
            <small>{meal.member_count} 人</small>
          </summary>
          <ul>
            {meal.members
              .filter(
                (member) =>
                  member.membership_status === "host" || member.membership_status === "member",
              )
              .map((member) => (
                <li key={member.user_id}>
                  <span>{member.display_name.slice(0, 1)}</span>
                  <div>
                    <strong>{member.display_name}</strong>
                    <small>
                      {member.membership_status === "host"
                        ? "發起人"
                        : member.tags.join(" · ") || "飯友"}
                    </small>
                  </div>
                  {meal.can_manage && member.membership_status === "member" ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void act(() => removeMealMember(meal.id, member.user_id))}
                    >
                      移除
                    </button>
                  ) : null}
                </li>
              ))}
          </ul>
        </details>

        {error ? (
          <p className="meal-form-error" role="alert">
            {error}
          </p>
        ) : null}
        <footer className="meal-detail-page__actions">
          {meal.status === "decided" ? (
            <span className="meal-result-label">
              <IconCheck aria-hidden="true" />
              餐廳已選定
            </span>
          ) : null}
          {meal.my_membership_status === "pending" ? (
            <span className="meal-pending-label">等待發起人接受申請</span>
          ) : null}
          {canLeave ? (
            <button
              type="button"
              className="button button--secondary"
              disabled={busy}
              onClick={() => void act(() => leaveMeal(meal.id))}
            >
              {meal.my_membership_status === "pending" ? "撤回申請" : "退出約飯"}
            </button>
          ) : null}
          {canCancel ? (
            <button
              type="button"
              className="button button--danger"
              disabled={busy}
              onClick={() => {
                if (window.confirm("確定要解除這場約飯嗎？解除後會立即從公開列表移除。"))
                  void act(() => cancelMeal(meal.id));
              }}
            >
              解除約飯
            </button>
          ) : null}
          {/* Backend is authoritative; the local status guard also prevents a stale response from
              briefly showing a second application action. / 後端為權限來源，前端再避免舊資料閃現重複申請。 */}
          {meal.can_join && meal.my_membership_status !== "pending" ? (
            <button
              type="button"
              className="button button--primary"
              disabled={busy}
              onClick={() => void act(() => joinMeal(meal.id))}
            >
              {meal.visibility === "private" ? "申請加入" : "加入約飯"}
            </button>
          ) : null}
        </footer>
      </article>
    </main>
  );
}
