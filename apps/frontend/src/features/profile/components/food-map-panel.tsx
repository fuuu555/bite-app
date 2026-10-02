"use client";

import { IconMap2, IconUserCheck, IconUsers } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  fetchFollowers,
  fetchFollowing,
  type FollowSummary,
} from "@/features/profile/api/social-api";

function FollowAvatar({ person }: { person: FollowSummary }) {
  return person.avatar_url ? (
    // Follow list avatars use the same public profile URL contract as chat avatars.
    // 追蹤列表頭像沿用公開個人資料的網址契約。
    // eslint-disable-next-line @next/next/no-img-element
    <img className="friends-hub-avatar" src={person.avatar_url} alt="" />
  ) : (
    <span className="friends-hub-avatar friends-hub-avatar--fallback" aria-hidden="true">
      {person.display_name.slice(0, 1)}
    </span>
  );
}

function FollowList({ title, people }: { title: string; people: FollowSummary[] }) {
  const router = useRouter();
  return (
    <section className="friends-hub__section" aria-labelledby={`${title}-title`}>
      <div className="friends-hub__section-heading">
        <h3 id={`${title}-title`}>{title}</h3>
        <span>{people.length} 位</span>
      </div>
      {people.length > 0 ? (
        <div className="friends-hub__list">
          {people.map((person) => (
            <div className="friends-hub__friend" key={person.id}>
              <FollowAvatar person={person} />
              <strong>{person.display_name}</strong>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => router.push(`/profiles/${person.id}`)}
              >
                查看
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="friends-hub__empty">
          {title === "追蹤中" ? "還沒有追蹤任何人。" : "目前還沒有追蹤者。"}
        </p>
      )}
    </section>
  );
}

export function FoodMapPanel() {
  const [following, setFollowing] = useState<FollowSummary[]>([]);
  const [followers, setFollowers] = useState<FollowSummary[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetchFollowing(controller.signal), fetchFollowers(controller.signal)])
      .then(([loadedFollowing, loadedFollowers]) => {
        setFollowing(loadedFollowing);
        setFollowers(loadedFollowers);
        setState("ready");
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("error");
      });
    return () => controller.abort();
  }, []);

  return (
    <section className="friends-hub food-map-panel" aria-labelledby="food-map-title">
      <div className="friends-hub__heading">
        <div className="profile-section-title">
          <IconMap2 aria-hidden="true" />
          <h2 id="food-map-title">美食地圖</h2>
        </div>
        <p>探索店家，也在這裡查看你追蹤的飯友。</p>
      </div>
      <button
        type="button"
        className="button button--secondary"
        disabled
        title="美食地圖入口尚未開放"
      >
        <IconMap2 aria-hidden="true" /> 開啟美食地圖
      </button>
      {state === "loading" ? <p className="friends-hub__state">正在整理追蹤資料…</p> : null}
      {state === "error" ? (
        <p className="friends-hub__error" role="alert">
          追蹤資料暫時無法載入。
        </p>
      ) : null}
      {state === "ready" ? (
        <>
          <div className="friends-hub__heading">
            <div className="profile-section-title">
              <IconUserCheck aria-hidden="true" />
              <h2>追蹤</h2>
              <span>
                {following.length} 個追蹤中 · {followers.length} 位追蹤者
              </span>
            </div>
          </div>
          <FollowList title="追蹤中" people={following} />
          <FollowList title="追蹤者" people={followers} />
        </>
      ) : null}
      {state === "ready" && following.length === 0 && followers.length === 0 ? (
        <div className="profile-tab-empty">
          <IconUsers aria-hidden="true" />
          <h3>開始建立你的美食圈</h3>
          <p>在公開個人頁追蹤喜歡一起吃飯的人。</p>
        </div>
      ) : null}
    </section>
  );
}
