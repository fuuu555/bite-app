import { describe, expect, it } from "vitest";

import { departedMealMembers, type Meal, type MealMember } from "./meals-api";

function member(userId: string, status: MealMember["membership_status"]): MealMember {
  return {
    user_id: userId,
    display_name: userId,
    avatar_url: null,
    tags: [],
    bio: null,
    meal_count: null,
    membership_status: status,
  };
}

function meal(members: MealMember[]): Meal {
  return {
    id: "meal-1",
    visibility: "public",
    title: "測試飯局",
    description: null,
    scheduled_at: "2026-10-01T12:00:00Z",
    join_deadline: "2026-10-01T11:45:00Z",
    capacity: 4,
    status: "open",
    host: members[0],
    members,
    member_count: members.filter(
      (item) => item.membership_status === "host" || item.membership_status === "member",
    ).length,
    candidates: [],
    decided_restaurant: null,
    my_membership_status: "host",
    my_vote_candidate_id: null,
    can_join: false,
    can_vote: false,
    can_manage: true,
  };
}

describe("departedMealMembers", () => {
  it("finds a formal member removed from the latest snapshot", () => {
    const host = member("host", "host");
    const guest = member("guest", "member");

    expect(departedMealMembers(meal([host, guest]), meal([host]))).toEqual([guest]);
  });

  it("does not treat a pending application change as a member departure", () => {
    const host = member("host", "host");
    const applicant = member("applicant", "pending");

    expect(departedMealMembers(meal([host, applicant]), meal([host]))).toEqual([]);
  });
});
