"use client";

import {
  IconArrowRight,
  IconCalendarEvent,
  IconCheck,
  IconChevronRight,
  IconPlus,
  IconSearch,
  IconSparkles,
  IconUsers,
  IconX,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MealCreateDialog as DraftMealCreateDialog } from "@/components/user/meal-create-dialog";

import { type ExploreRestaurant, fetchExploreRestaurants } from "@/lib/explore-api";
import {
  addMealCandidate,
  castMealVote,
  cancelMeal,
  fetchMeals,
  finalizeMealVote,
  type Meal,
  type MealRestaurant,
  MealsApiError,
  removeMealCandidate,
  reviewMealMember,
  startMealWithCurrentMembers,
  startMealVoting,
} from "@/lib/meals-api";

type MealTab = "public" | "mine";
type RestaurantChoice = Pick<
  MealRestaurant,
  "id" | "name" | "address" | "cuisine_name" | "photo_url"
>;
function toRestaurantChoice(restaurant: ExploreRestaurant): RestaurantChoice {
  return {
    id: restaurant.id,
    name: restaurant.name,
    address: restaurant.address,
    cuisine_name: restaurant.primary_cuisine.display_name,
    photo_url: restaurant.photo_url,
  };
}

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
  if (meal.status === "awaiting_host_decision") return "等待確認";
  if (meal.status === "voting") return "投票中";
  if (meal.status === "decided") return "已成團";
  if (meal.member_count >= meal.capacity) return "已額滿";
  return meal.visibility === "private" ? "開放申請" : "可加入";
}

function actionError(error: unknown) {
  if (error instanceof MealsApiError && typeof error.detail === "string") return error.detail;
  return "這個操作暫時無法完成，請再試一次。";
}

function useRestaurantSearch(query: string) {
  const [searchState, setSearchState] = useState<{
    query: string;
    results: RestaurantChoice[];
  }>({ query: "", results: [] });

  useEffect(() => {
    const normalizedQuery = query.trim();
    if (!normalizedQuery) return;

    // Debounce restaurant lookup so fast typing does not issue one request per keystroke.
    // 餐廳搜尋加入短暫延遲，避免快速輸入時每個字都送出一次請求。
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchExploreRestaurants(
        normalizedQuery,
        { cuisineId: "", priceRange: "", distanceKm: "" },
        undefined,
        controller.signal,
      )
        .then((response) =>
          setSearchState({
            query: normalizedQuery,
            results: response.restaurants.map(toRestaurantChoice),
          }),
        )
        .catch(() => {
          if (!controller.signal.aborted) {
            setSearchState({ query: normalizedQuery, results: [] });
          }
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return searchState.query === query.trim() ? searchState.results : [];
}

function AvatarStack({ meal }: { meal: Meal }) {
  return (
    <div className="meal-card__avatars" aria-label={`${meal.member_count} 位參與者`}>
      {meal.members.slice(0, 4).map((member) => (
        <span key={member.user_id} title={member.display_name} aria-label={member.display_name}>
          {member.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={member.avatar_url} alt="" />
          ) : (
            member.display_name.slice(0, 1)
          )}
        </span>
      ))}
      {meal.member_count > 4 ? <small>+{meal.member_count - 4}</small> : null}
    </div>
  );
}

function RestaurantVisual({ restaurant }: { restaurant: MealRestaurant }) {
  if (restaurant.photo_url) {
    return (
      <div className="meal-card__visual has-photo">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={restaurant.photo_url} alt="" />
      </div>
    );
  }
  return (
    <div className="meal-card__visual" aria-hidden="true">
      {restaurant.name.slice(0, 1)}
    </div>
  );
}

function MealCard({ meal }: { meal: Meal }) {
  const restaurant = meal.decided_restaurant ?? meal.candidates[0]?.restaurant ?? null;
  const detailLabel = meal.can_manage
    ? "管理飯局"
    : meal.can_vote
      ? "前往投票"
      : meal.can_join
        ? meal.visibility === "private"
          ? "查看並申請"
          : "查看並加入"
        : meal.my_membership_status === "pending"
          ? "查看申請"
          : "查看飯局";

  return (
    <article className={`meal-card meal-card--${meal.status}`}>
      <div className="meal-card__topline">
        <span className={`meal-status is-${meal.status}`}>{statusLabel(meal)}</span>
        <span>{meal.visibility === "private" ? "私人約飯" : "公開加入"}</span>
      </div>
      <div className="meal-card__body">
        <div>
          <p className="meal-card__host">{meal.host.display_name} 發起</p>
          <h2>{meal.title}</h2>
          {meal.description ? <p className="meal-card__description">{meal.description}</p> : null}
          <dl className="meal-card__facts">
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
        </div>
        {restaurant ? <RestaurantVisual restaurant={restaurant} /> : null}
      </div>
      <div className="meal-card__restaurant">
        {restaurant ? (
          <Link href={`/restaurants/${restaurant.id}`}>
            <span>
              <strong>{restaurant.name}</strong>
              <small>
                {restaurant.cuisine_name || "餐廳"} · {restaurant.address}
              </small>
            </span>
            <IconChevronRight aria-hidden="true" />
          </Link>
        ) : (
          <span className="meal-card__undecided">
            <IconSparkles aria-hidden="true" /> 餐廳尚未決定，集合後一起投票
          </span>
        )}
      </div>
      <footer className="meal-card__footer">
        <AvatarStack meal={meal} />
        <div className="meal-card__actions">
          <Link className="button button--primary" href={`/meals/${meal.id}`}>
            {detailLabel}
            <IconArrowRight aria-hidden="true" />
          </Link>
        </div>
      </footer>
    </article>
  );
}

export function MealDetail({
  meal,
  onChange,
  onError,
}: {
  meal: Meal;
  onChange: (meal: Meal) => void;
  onError: (message: string) => void;
}) {
  const [candidateQuery, setCandidateQuery] = useState("");
  const results = useRestaurantSearch(candidateQuery);
  const [busy, setBusy] = useState(false);

  const act = async (operation: () => Promise<Meal>) => {
    setBusy(true);
    try {
      onChange(await operation());
    } catch (error) {
      onError(actionError(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="meal-detail" aria-label="約飯操作">
      {meal.can_manage && meal.status === "awaiting_host_decision" ? (
        <div className="meal-detail__panel meal-capacity-decision" role="status">
          <h2>加入截止時間已到</h2>
          <p>
            目前 {meal.member_count} / {meal.capacity} 人。要以目前人數開始，還是解除這場約飯？
          </p>
          <div>
            <button
              type="button"
              className="button button--danger"
              disabled={busy}
              onClick={() => {
                if (window.confirm("確定要解除這場約飯嗎？")) {
                  void act(() => cancelMeal(meal.id));
                }
              }}
            >
              解除約飯
            </button>
            <button
              type="button"
              className="button button--primary"
              disabled={busy}
              onClick={() => void act(() => startMealWithCurrentMembers(meal.id))}
            >
              以 {meal.member_count} 人開始 <IconArrowRight aria-hidden="true" />
            </button>
          </div>
        </div>
      ) : null}
      {meal.can_manage &&
      meal.visibility === "private" &&
      meal.members.some((member) => member.membership_status === "pending") ? (
        <div className="meal-detail__panel">
          <h2>待審核申請</h2>
          {meal.members
            .filter((member) => member.membership_status === "pending")
            .map((member) => (
              <div className="meal-applicant" key={member.user_id}>
                <span>{member.display_name.slice(0, 1)}</span>
                <p>
                  <strong>{member.display_name}</strong>
                  <small>{member.tags.join(" · ") || "尚未設定 Tag"}</small>
                </p>
                <div>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act(() => reviewMealMember(meal.id, member.user_id, false))}
                  >
                    略過
                  </button>
                  <button
                    type="button"
                    className="button button--primary"
                    disabled={busy}
                    onClick={() => void act(() => reviewMealMember(meal.id, member.user_id, true))}
                  >
                    接受
                  </button>
                </div>
              </div>
            ))}
        </div>
      ) : null}
      {meal.visibility === "public" &&
      (meal.status === "open" || meal.status === "awaiting_host_decision") &&
      !meal.decided_restaurant &&
      (meal.can_manage || meal.candidates.length > 0) ? (
        <div className="meal-detail__panel">
          <header>
            <div>
              <h2>候選餐廳</h2>
              <p>最多三家。額滿時會進入投票；截止後由你確認是否以目前人數開始。</p>
            </div>
            <span>{meal.candidates.length} / 3</span>
          </header>
          <div className="meal-candidate-list">
            {meal.candidates.map((candidate) => (
              <div key={candidate.id}>
                <span>{candidate.position}</span>
                <p>
                  <strong>{candidate.restaurant.name}</strong>
                  <small>{candidate.restaurant.cuisine_name || "餐廳"}</small>
                </p>
                {meal.can_manage ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void act(() => removeMealCandidate(meal.id, candidate.id))}
                    aria-label={`移除 ${candidate.restaurant.name}`}
                  >
                    <IconX aria-hidden="true" />
                  </button>
                ) : null}
              </div>
            ))}
          </div>
          {meal.can_manage && meal.candidates.length < 3 ? (
            <div className="meal-candidate-search">
              <label htmlFor={`candidate-search-${meal.id}`}>搜尋已發布餐廳</label>
              <div>
                <IconSearch aria-hidden="true" />
                <input
                  id={`candidate-search-${meal.id}`}
                  value={candidateQuery}
                  onChange={(event) => setCandidateQuery(event.target.value)}
                  placeholder="輸入店名"
                />
              </div>
              {candidateQuery.trim() && results.length ? (
                <ul>
                  {results.slice(0, 5).map((restaurant) => (
                    <li key={restaurant.id}>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          setCandidateQuery("");
                          void act(() => addMealCandidate(meal.id, restaurant.id));
                        }}
                      >
                        <span>
                          <strong>{restaurant.name}</strong>
                          <small>{restaurant.cuisine_name || "餐廳"}</small>
                        </span>
                        <IconPlus aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {meal.can_manage && meal.status === "open" ? (
            <button
              type="button"
              className="meal-start-vote"
              disabled={busy || meal.candidates.length === 0}
              onClick={() => void act(() => startMealVoting(meal.id))}
            >
              提前開始投票 <IconArrowRight aria-hidden="true" />
            </button>
          ) : null}
        </div>
      ) : null}
      {meal.status === "voting" ? (
        <div className="meal-detail__panel meal-vote-panel">
          <header>
            <div>
              <h2>選一間想去的</h2>
              <p>每位正式成員一票，可以在結果確認前改選。</p>
            </div>
            <span>{meal.can_vote ? "正式成員可投票" : "加入後可查看票數"}</span>
          </header>
          <div className="meal-vote-options">
            {meal.candidates.map((candidate) => {
              const selected = meal.my_vote_candidate_id === candidate.id;
              return (
                <div
                  key={candidate.id}
                  className={`meal-vote-option${selected ? " is-selected" : ""}`}
                >
                  <button
                    type="button"
                    className="meal-vote-option__choice"
                    disabled={busy || !meal.can_vote}
                    onClick={() => void act(() => castMealVote(meal.id, candidate.id))}
                  >
                    <span className="meal-vote-options__check">
                      {selected ? <IconCheck aria-hidden="true" /> : null}
                    </span>
                    <span>
                      <strong>{candidate.restaurant.name}</strong>
                      <small>{candidate.restaurant.cuisine_name || "餐廳"}</small>
                    </span>
                    {candidate.vote_count !== null ? <b>{candidate.vote_count} 票</b> : null}
                  </button>
                  <Link
                    className="meal-vote-option__restaurant"
                    href={`/restaurants/${candidate.restaurant.id}`}
                    aria-label={`查看 ${candidate.restaurant.name}`}
                  >
                    查看餐廳 <IconChevronRight aria-hidden="true" />
                  </Link>
                </div>
              );
            })}
          </div>
          {meal.can_manage ? (
            <button
              type="button"
              className="button button--primary"
              disabled={busy}
              onClick={() => void act(() => finalizeMealVote(meal.id))}
            >
              確認投票結果 <IconArrowRight aria-hidden="true" />
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function MealsPage({
  initialRestaurantId,
  compose = false,
  cancelled = null,
}: {
  initialRestaurantId?: string;
  compose?: boolean;
  cancelled?: "self" | "host" | null;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<MealTab>("public");
  const [meals, setMeals] = useState<Meal[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [createOpen, setCreateOpen] = useState(Boolean(initialRestaurantId) || compose);
  const [cancelledNotice, setCancelledNotice] = useState<"self" | "host" | null>(cancelled);

  useEffect(() => {
    if (!cancelledNotice) return;
    const timer = window.setTimeout(() => {
      setCancelledNotice(null);
      window.history.replaceState({}, "", "/meals");
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [cancelledNotice]);

  useEffect(() => {
    let active = true;
    let refreshing = false;
    let loadedOnce = false;
    const controller = new AbortController();
    const loadMeals = async () => {
      if (refreshing || controller.signal.aborted) return;
      refreshing = true;
      try {
        const { meals: nextMeals } = await fetchMeals(tab, controller.signal);
        if (!active) return;
        loadedOnce = true;
        setMeals(nextMeals);
        setState("ready");
      } catch {
        // A background refresh failure must not erase the last useful list.
        // 背景更新失敗時保留既有飯局，只有首次載入失敗才顯示錯誤狀態。
        if (active && !controller.signal.aborted && !loadedOnce) setState("error");
      } finally {
        refreshing = false;
      }
    };
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void loadMeals();
    };
    const refreshOnFocus = () => void loadMeals();

    void loadMeals();
    const refreshTimer = window.setInterval(() => void loadMeals(), 10_000);
    window.addEventListener("focus", refreshOnFocus);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      active = false;
      controller.abort();
      window.clearInterval(refreshTimer);
      window.removeEventListener("focus", refreshOnFocus);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [tab]);

  const selectTab = (nextTab: MealTab) => {
    if (nextTab === tab) return;
    setState("loading");
    setTab(nextTab);
  };
  const created = (meal: Meal) => {
    setCreateOpen(false);
    router.push(`/meals/${meal.id}`);
  };

  return (
    <main className="meals-page">
      <header className="meals-page__header">
        <div>
          <h1>今天，想和誰吃一餐？</h1>
          <span>從一個約飯開始，找到同樣在意這一口的人。</span>
        </div>
        <button
          type="button"
          className="button button--primary"
          onClick={() => setCreateOpen(true)}
        >
          <IconPlus aria-hidden="true" />
          發起約飯
        </button>
      </header>
      <nav className="meal-tabs" aria-label="約飯篩選">
        <button
          type="button"
          className={tab === "public" ? "is-active" : ""}
          onClick={() => selectTab("public")}
        >
          公開約飯
        </button>
        <button
          type="button"
          className={tab === "mine" ? "is-active" : ""}
          onClick={() => selectTab("mine")}
        >
          我的約飯
        </button>
      </nav>
      {cancelledNotice ? (
        <p className="meal-feedback is-success" role="status">
          <IconCheck aria-hidden="true" />
          {cancelledNotice === "host"
            ? "發起人已解除約飯，飯局已從列表移除。"
            : "約飯已解除，已從目前列表移除。"}
        </p>
      ) : null}
      {state === "loading" ? (
        <section className="meal-loading" aria-label="正在載入約飯">
          <span />
          <span />
          <span />
        </section>
      ) : null}
      {state === "error" ? (
        <section className="meal-state">
          <h2>約飯資料暫時無法載入</h2>
          <p>請重新整理頁面後再試一次。</p>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => window.location.reload()}
          >
            重新整理
          </button>
        </section>
      ) : null}
      {state === "ready" && meals.length === 0 ? (
        <section className="meal-state">
          <div>
            <IconUsers aria-hidden="true" />
          </div>
          <h2>{tab === "mine" ? "還沒有進行中的約飯" : "這裡還沒有可加入的約飯"}</h2>
          <p>
            {tab === "mine"
              ? "你建立或加入的飯局會出現在這裡。"
              : "不如由你先開一桌，讓同樣想吃的人找到你。"}
          </p>
        </section>
      ) : null}
      {state === "ready" && meals.length ? (
        <section className="meal-list" aria-label="約飯列表">
          {meals.map((meal) => (
            <MealCard key={meal.id} meal={meal} />
          ))}
        </section>
      ) : null}
      {createOpen ? (
        <DraftMealCreateDialog
          initialRestaurantId={initialRestaurantId}
          onClose={() => {
            setCreateOpen(false);
            window.history.replaceState({}, "", "/meals");
          }}
          onCreated={created}
        />
      ) : null}
    </main>
  );
}
