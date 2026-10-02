/** Meal and voting API client / 約飯與投票 API Client。 */

export type MealVisibility = "public" | "private";
export type MealStatus =
  "open" | "awaiting_host_decision" | "voting" | "decided" | "cancelled" | "completed";
export type MealMembershipStatus = "host" | "member" | "pending" | "rejected" | "left" | "removed";

export type MealMember = {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  tags: string[];
  bio: string | null;
  meal_count: number | null;
  membership_status: MealMembershipStatus;
};

export type MealRestaurant = {
  id: string;
  name: string;
  address: string;
  cuisine_name: string | null;
  photo_url: string | null;
};

export type MealCandidate = {
  id: string;
  position: number;
  restaurant: MealRestaurant;
  vote_count: number | null;
};

export type Meal = {
  id: string;
  visibility: MealVisibility;
  title: string;
  description: string | null;
  scheduled_at: string;
  join_deadline: string | null;
  capacity: number;
  status: MealStatus;
  host: MealMember;
  members: MealMember[];
  member_count: number;
  candidates: MealCandidate[];
  decided_restaurant: MealRestaurant | null;
  my_membership_status: MealMembershipStatus | null;
  my_vote_candidate_id: string | null;
  can_join: boolean;
  can_vote: boolean;
  can_manage: boolean;
};

export type MealCreateInput = {
  visibility: MealVisibility;
  title: string;
  description: string | null;
  scheduled_at: string;
  join_deadline: string | null;
  capacity: number;
  restaurant_mode: "direct" | "vote";
  restaurant_id: string | null;
};

export function departedMealMembers(previous: Meal, next: Meal) {
  const nextFormalMemberIds = new Set(
    next.members
      .filter(
        (member) => member.membership_status === "host" || member.membership_status === "member",
      )
      .map((member) => member.user_id),
  );
  // Compare formal membership snapshots only; pending application changes use their own workflow.
  // 只比較正式成員快照，待審核申請的異動仍由審核流程呈現。
  return previous.members.filter(
    (member) =>
      (member.membership_status === "host" || member.membership_status === "member") &&
      !nextFormalMemberIds.has(member.user_id),
  );
}

export class MealsApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : "約飯操作暫時無法完成");
  }
}

async function mealsApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new MealsApiError(response.status, payload.detail);
  }
  return (await response.json()) as T;
}

export function fetchMeals(scope: "public" | "mine", signal?: AbortSignal) {
  return mealsApi<{ meals: Meal[] }>(`/meals?scope=${scope}`, { signal });
}

export function fetchMeal(mealId: string, signal?: AbortSignal) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}`, { signal });
}

export function createMeal(payload: MealCreateInput) {
  return mealsApi<Meal>("/meals", { method: "POST", body: JSON.stringify(payload) });
}

export function joinMeal(mealId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/join`, { method: "POST" });
}

export function leaveMeal(mealId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/leave`, { method: "POST" });
}

export function cancelMeal(mealId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/cancel`, { method: "POST" });
}

export function addMealCandidate(mealId: string, restaurantId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/candidates`, {
    method: "POST",
    body: JSON.stringify({ restaurant_id: restaurantId }),
  });
}

export function removeMealCandidate(mealId: string, candidateId: string) {
  return mealsApi<Meal>(
    `/meals/${encodeURIComponent(mealId)}/candidates/${encodeURIComponent(candidateId)}`,
    { method: "DELETE" },
  );
}

export function startMealVoting(mealId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/start-voting`, { method: "POST" });
}

export function startMealWithCurrentMembers(mealId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/start-with-current-members`, {
    method: "POST",
  });
}

export function castMealVote(mealId: string, candidateId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/votes`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export function finalizeMealVote(mealId: string) {
  return mealsApi<Meal>(`/meals/${encodeURIComponent(mealId)}/finalize-vote`, { method: "POST" });
}

export function reviewMealMember(mealId: string, userId: string, approved: boolean) {
  return mealsApi<Meal>(
    `/meals/${encodeURIComponent(mealId)}/members/${encodeURIComponent(userId)}/${approved ? "approve" : "reject"}`,
    { method: "POST" },
  );
}

export function removeMealMember(mealId: string, userId: string) {
  return mealsApi<Meal>(
    `/meals/${encodeURIComponent(mealId)}/members/${encodeURIComponent(userId)}/remove`,
    { method: "POST" },
  );
}
