import { expect, test } from "@playwright/test";

import { mockSignedInUser } from "./user-session";

const mealId = "00000000-0000-4000-8000-000000000101";
const userId = "00000000-0000-4000-8000-000000000001";

const meal = {
  id: mealId,
  visibility: "public",
  title: "週五下班吃拉麵",
  description: "在捷運站集合",
  scheduled_at: "2026-10-09T11:00:00Z",
  join_deadline: "2026-10-09T10:00:00Z",
  capacity: 4,
  status: "open",
  host: {
    user_id: userId,
    display_name: "小咬",
    avatar_url: null,
    tags: [],
    bio: null,
    meal_count: 2,
    membership_status: "host",
  },
  members: [
    {
      user_id: userId,
      display_name: "小咬",
      avatar_url: null,
      tags: [],
      bio: null,
      meal_count: 2,
      membership_status: "host",
    },
  ],
  member_count: 1,
  candidates: [],
  decided_restaurant: null,
  my_membership_status: "host",
  my_vote_candidate_id: null,
  can_join: false,
  can_vote: false,
  can_manage: true,
};

test("meal member can send and receive a text message over the shared WebSocket", async ({
  page,
}) => {
  await mockSignedInUser(page, { mockRealtime: false });
  await page.route(new RegExp(`/api/v1/meals/${mealId}$`), async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(meal) });
  });
  await page.route(new RegExp(`/api/v1/meals/${mealId}/messages`), async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ messages: [], next_cursor: null }),
    });
  });

  let subscribedToChat = false;
  await page.routeWebSocket(/\/api\/v1\/ws$/, (socket) => {
    socket.onMessage((rawMessage) => {
      const request = JSON.parse(String(rawMessage)) as {
        type: string;
        request_id: string;
        channel?: string;
        meal_id?: string;
        content?: string;
      };
      if (request.type === "subscribe") {
        if (request.channel === "chat" && request.meal_id === mealId) subscribedToChat = true;
        socket.send(
          JSON.stringify({
            type: "subscribed",
            request_id: request.request_id,
            channel: request.channel,
            meal_id: request.meal_id,
          }),
        );
        return;
      }
      if (request.type === "message.send") {
        const messageId = "00000000-0000-4000-8000-000000000201";
        socket.send(
          JSON.stringify({
            type: "message.created",
            meal_id: mealId,
            message: {
              id: messageId,
              conversation_id: "00000000-0000-4000-8000-000000000301",
              meal_id: mealId,
              sender: { user_id: userId, display_name: "小咬", avatar_url: null },
              content: request.content,
              created_at: "2026-10-01T12:00:00Z",
            },
          }),
        );
        socket.send(
          JSON.stringify({ type: "ack", request_id: request.request_id, message_id: messageId }),
        );
      }
    });
    socket.send(JSON.stringify({ type: "ready" }));
  });

  await page.goto(`/meals/${mealId}`);

  await expect(page.getByRole("heading", { name: meal.title })).toBeVisible();
  await expect(page.getByText("即時連線中")).toBeVisible();
  await expect.poll(() => subscribedToChat).toBe(true);

  await page.getByLabel("傳送訊息").fill("我會提早五分鐘到");
  await page.getByRole("button", { name: "傳送", exact: true }).click();

  await expect(page.getByText("我會提早五分鐘到")).toBeVisible();
  await expect(page.getByLabel("傳送訊息")).toHaveValue("");
});
