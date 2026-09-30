"use client";

import {
  IconCheck,
  IconChevronDown,
  IconEdit,
  IconHeart,
  IconHistory,
  IconLoader2,
  IconMessageCircle,
  IconSend,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createRestaurantReview,
  deleteRestaurantReview,
  fetchRestaurantReviews,
  fetchReviewTimeline,
  RestaurantReview,
  ReviewReason,
  ReviewsApiError,
  RevisitStatus,
  ReviewSort,
  ReviewStatusFilter,
  toggleReviewLike,
  updateRestaurantReview,
} from "@/lib/reviews-api";

const statusLabels: Record<RevisitStatus, string> = {
  will_return: "會再訪",
  neutral: "普通",
  will_not_return: "不會",
};

const sortLabels: Record<ReviewSort, string> = {
  featured: "綜合",
  latest: "最新",
  popular: "熱門",
};

const statusFilters: Array<{ value: ReviewStatusFilter; label: string }> = [
  { value: "all", label: "全部狀態" },
  { value: "will_return", label: "會再訪" },
  { value: "neutral", label: "普通" },
  { value: "will_not_return", label: "不會" },
];

type ReviewDraft = {
  content: string;
  revisit_status: RevisitStatus;
  reason_ids: string[];
};

const emptyDraft: ReviewDraft = {
  content: "",
  revisit_status: "will_return",
  reason_ids: [],
};

function formatReviewDate(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    month: "numeric",
    day: "numeric",
  }).format(new Date(value));
}

function ReviewAvatar({ review }: { review: RestaurantReview }) {
  return review.author_avatar_url ? (
    // Keep the public avatar URL contract until signed storage is added.
    // 完成簽名儲存前，沿用目前可驗證的公開頭像 URL。
    // eslint-disable-next-line @next/next/no-img-element
    <img src={review.author_avatar_url} alt="" className="restaurant-review__avatar" />
  ) : (
    <span
      className="restaurant-review__avatar restaurant-review__avatar--fallback"
      aria-hidden="true"
    >
      {review.author_display_name.slice(0, 1)}
    </span>
  );
}

function ReviewForm({
  draft,
  reasons,
  busy,
  submitLabel,
  onChange,
  onSubmit,
  onCancel,
}: {
  draft: ReviewDraft;
  reasons: ReviewReason[];
  busy: boolean;
  submitLabel: string;
  onChange: (draft: ReviewDraft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel?: () => void;
}) {
  const positiveReasons = reasons.filter((reason) => reason.polarity === "positive");
  const negativeReasons = reasons.filter((reason) => reason.polarity === "negative");
  const toggleReason = (reasonId: string) => {
    const reasonIds = draft.reason_ids.includes(reasonId)
      ? draft.reason_ids.filter((id) => id !== reasonId)
      : [...draft.reason_ids, reasonId];
    onChange({ ...draft, reason_ids: reasonIds.slice(0, 5) });
  };

  return (
    <form className="restaurant-review-form" onSubmit={onSubmit}>
      <label htmlFor="review-content">這次吃得如何？</label>
      <textarea
        id="review-content"
        value={draft.content}
        onChange={(event) => onChange({ ...draft, content: event.target.value })}
        placeholder="寫下你會想留給下一個人的一句話…"
        maxLength={2000}
        required
        rows={4}
      />
      <fieldset>
        <legend>你會再訪嗎？</legend>
        <div className="restaurant-review-form__status-options">
          {(Object.keys(statusLabels) as RevisitStatus[]).map((status) => (
            <label
              key={status}
              className={`restaurant-review-status-option${draft.revisit_status === status ? " is-active" : ""}`}
            >
              <input
                type="radio"
                name="revisit-status"
                value={status}
                checked={draft.revisit_status === status}
                onChange={() => onChange({ ...draft, revisit_status: status })}
              />
              <span>{statusLabels[status]}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {reasons.length > 0 ? (
        <fieldset>
          <legend>想補充哪些原因？（可複選）</legend>
          <div className="restaurant-review-reasons">
            {[...positiveReasons, ...negativeReasons].map((reason) => (
              <button
                key={reason.id}
                type="button"
                className={draft.reason_ids.includes(reason.id) ? "is-active" : undefined}
                onClick={() => toggleReason(reason.id)}
                aria-pressed={draft.reason_ids.includes(reason.id)}
              >
                {draft.reason_ids.includes(reason.id) ? <IconCheck aria-hidden="true" /> : null}
                {reason.display_name}
              </button>
            ))}
          </div>
        </fieldset>
      ) : null}
      <div className="restaurant-review-form__actions">
        {onCancel ? (
          <button type="button" className="button button--ghost" onClick={onCancel} disabled={busy}>
            取消
          </button>
        ) : null}
        <button
          type="submit"
          className="button button--primary"
          disabled={busy || !draft.content.trim()}
        >
          {busy ? (
            <IconLoader2 className="is-spinning" aria-hidden="true" />
          ) : (
            <IconSend aria-hidden="true" />
          )}
          {submitLabel}
        </button>
      </div>
    </form>
  );
}

function ReviewCard({
  restaurantId,
  review,
  availableReasons,
  onChanged,
  onError,
}: {
  restaurantId: string;
  review: RestaurantReview;
  availableReasons: ReviewReason[];
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [liked, setLiked] = useState(review.liked_by_me);
  const [likeCount, setLikeCount] = useState(review.like_count);
  const [timeline, setTimeline] = useState<RestaurantReview[] | null>(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [draft, setDraft] = useState<ReviewDraft>({
    content: review.content,
    revisit_status: review.revisit_status,
    reason_ids: review.reasons.map((reason) => reason.id),
  });

  const toggleLike = async () => {
    const nextLiked = !liked;
    setLiked(nextLiked);
    setLikeCount((count) => count + (nextLiked ? 1 : -1));
    try {
      const result = await toggleReviewLike(review.id, nextLiked);
      setLikeCount(result.like_count);
    } catch (error) {
      setLiked(!nextLiked);
      setLikeCount((count) => count - (nextLiked ? 1 : -1));
      onError(
        error instanceof ReviewsApiError && error.status === 401
          ? "請先登入再按讚。"
          : "按讚失敗，請再試一次。",
      );
    }
  };

  const saveEdit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      await updateRestaurantReview(review.id, draft);
      setEditing(false);
      onChanged();
    } catch (error) {
      onError(
        error instanceof ReviewsApiError ? "留言目前無法更新，請再試一次。" : "留言目前無法更新。",
      );
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    setBusy(true);
    try {
      await deleteRestaurantReview(review.id);
      setDeleting(false);
      onChanged();
    } catch {
      onError("留言目前無法刪除，請再試一次。");
      setBusy(false);
    }
  };

  const showTimeline = async () => {
    if (timeline) {
      setTimeline(null);
      return;
    }
    setTimelineLoading(true);
    try {
      const result = await fetchReviewTimeline(restaurantId, review.id);
      setTimeline(result.reviews);
    } catch {
      onError("再訪紀錄目前無法載入，請再試一次。");
    } finally {
      setTimelineLoading(false);
    }
  };

  if (editing) {
    return (
      <article className="restaurant-review-card is-editing">
        <div className="restaurant-review-card__heading">
          <div className="restaurant-review-card__author">
            <ReviewAvatar review={review} />
            <strong>編輯你的留言</strong>
          </div>
        </div>
        <ReviewForm
          draft={draft}
          reasons={availableReasons}
          busy={busy}
          submitLabel="儲存修改"
          onChange={setDraft}
          onSubmit={saveEdit}
          onCancel={() => setEditing(false)}
        />
      </article>
    );
  }

  return (
    <article className="restaurant-review-card">
      <div className="restaurant-review-card__heading">
        <div className="restaurant-review-card__author">
          <ReviewAvatar review={review} />
          <div>
            <strong>{review.author_display_name}</strong>
            <span>{formatReviewDate(review.created_at)}</span>
          </div>
        </div>
        <span className={`restaurant-review-status is-${review.revisit_status}`}>
          {statusLabels[review.revisit_status]}
        </span>
      </div>
      <p className="restaurant-review-card__content">{review.content}</p>
      {review.reasons.length > 0 ? (
        <div className="restaurant-review-card__reasons" aria-label="留言原因">
          {review.reasons.map((reason) => (
            <span key={reason.id}>{reason.display_name}</span>
          ))}
        </div>
      ) : null}
      <div className="restaurant-review-card__meta">
        <span>{review.revisit_count} 次紀錄</span>
        {review.is_edited ? <span>已編輯</span> : null}
        <button type="button" onClick={showTimeline} disabled={timelineLoading}>
          {timelineLoading ? (
            <IconLoader2 className="is-spinning" aria-hidden="true" />
          ) : (
            <IconHistory aria-hidden="true" />
          )}
          {timeline ? "收起再訪紀錄" : "查看再訪紀錄"}
        </button>
      </div>
      {timeline ? (
        <div className="restaurant-review-timeline" aria-label="再訪時間線">
          {timeline.map((item, index) => (
            <div className="restaurant-review-timeline__item" key={item.id}>
              <span className="restaurant-review-timeline__dot" aria-hidden="true" />
              <div>
                <strong>
                  {item.is_deleted
                    ? "已刪除的紀錄"
                    : index === timeline.length - 1
                      ? "最新紀錄"
                      : `第 ${index + 1} 次`}
                </strong>
                <span>
                  {formatReviewDate(item.created_at)} · {statusLabels[item.revisit_status]}
                </span>
                <p>{item.is_deleted ? "此紀錄已刪除，仍保留在再訪時間線中。" : item.content}</p>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <div className="restaurant-review-card__actions">
        <button
          type="button"
          className={liked ? "is-liked" : undefined}
          onClick={toggleLike}
          aria-pressed={liked}
        >
          <IconHeart aria-hidden="true" />
          {likeCount > 0 ? likeCount : "有共鳴"}
        </button>
        {review.is_owner ? (
          <>
            <button type="button" onClick={() => setEditing(true)}>
              <IconEdit aria-hidden="true" /> 編輯
            </button>
            <button type="button" className="is-danger" onClick={() => setDeleting(true)}>
              <IconTrash aria-hidden="true" /> 刪除
            </button>
          </>
        ) : null}
      </div>
      {deleting ? (
        <div
          className="restaurant-review-delete-confirm"
          role="alertdialog"
          aria-label="確認刪除留言"
        >
          <div>
            <strong>確定要刪除這則留言嗎？</strong>
            <span>刪除後會從公開列表移除，但你的再訪時間線仍會保留。</span>
          </div>
          <div>
            <button
              type="button"
              className="button button--ghost"
              onClick={() => setDeleting(false)}
              disabled={busy}
            >
              保留留言
            </button>
            <button
              type="button"
              className="button button--danger"
              onClick={confirmDelete}
              disabled={busy}
            >
              {busy ? (
                <IconLoader2 className="is-spinning" aria-hidden="true" />
              ) : (
                <IconTrash aria-hidden="true" />
              )}
              確認刪除
            </button>
          </div>
        </div>
      ) : null}
    </article>
  );
}

export function RestaurantReviewsPanel({
  restaurantId,
  onReviewsChanged,
}: {
  restaurantId: string;
  onReviewsChanged: () => void;
}) {
  const [sort, setSort] = useState<ReviewSort>("featured");
  const [status, setStatus] = useState<ReviewStatusFilter>("all");
  const [reviews, setReviews] = useState<RestaurantReview[]>([]);
  const [reasons, setReasons] = useState<ReviewReason[]>([]);
  const [hasReviewHistory, setHasReviewHistory] = useState(false);
  const [loading, setLoading] = useState(true);
  const [composerOpen, setComposerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [draft, setDraft] = useState<ReviewDraft>(emptyDraft);

  const load = async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const result = await fetchRestaurantReviews(restaurantId, sort, status, signal);
      setReviews(result.reviews);
      setReasons(result.available_reasons);
      setHasReviewHistory(result.has_current_user_review);
    } catch (caught) {
      if (signal?.aborted) return;
      setError(
        caught instanceof ReviewsApiError && caught.status === 401
          ? "請先登入才能查看留言。"
          : "留言目前無法載入。",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchRestaurantReviews(restaurantId, sort, status, controller.signal)
      .then((result) => {
        setReviews(result.reviews);
        setReasons(result.available_reasons);
        setHasReviewHistory(result.has_current_user_review);
        setError("");
      })
      .catch((caught) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof ReviewsApiError && caught.status === 401
            ? "請先登入才能查看留言。"
            : "留言目前無法載入。",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [restaurantId, sort, status]);

  const onChanged = () => {
    void load();
    onReviewsChanged();
  };

  const submitReview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createRestaurantReview(restaurantId, draft);
      setDraft(emptyDraft);
      setComposerOpen(false);
      setSuccess("留言已發布，謝謝你留下這次紀錄。");
      onChanged();
      window.setTimeout(() => setSuccess(""), 3200);
    } catch (caught) {
      setError(
        caught instanceof ReviewsApiError && caught.status === 401
          ? "登入狀態已失效，請重新登入。"
          : "留言目前無法發布，請再試一次。",
      );
    } finally {
      setBusy(false);
    }
  };

  const statusSummary = useMemo(() => {
    const count = reviews.length;
    return count > 0 ? `${count} 則目前留言` : "還沒有符合條件的留言";
  }, [reviews.length]);

  return (
    <section className="restaurant-reviews-panel" aria-labelledby="restaurant-reviews-title">
      <div className="restaurant-reviews-panel__header">
        <div>
          <p className="restaurant-detail-v3__kicker">BiteMap / Notes</p>
          <h2 id="restaurant-reviews-title">
            <IconMessageCircle aria-hidden="true" /> 留言
          </h2>
          <p>留下真實的一次，讓下一個人更好決定。</p>
        </div>
        <button
          type="button"
          className="button button--primary"
          onClick={() => setComposerOpen((open) => !open)}
        >
          {composerOpen ? <IconX aria-hidden="true" /> : <IconMessageCircle aria-hidden="true" />}
          {composerOpen ? "先收起" : hasReviewHistory ? "再訪留言" : "留下紀錄"}
        </button>
      </div>
      {composerOpen ? (
        <ReviewForm
          draft={draft}
          reasons={reasons}
          busy={busy}
          submitLabel="發布留言"
          onChange={setDraft}
          onSubmit={submitReview}
          onCancel={() => setComposerOpen(false)}
        />
      ) : null}
      <div className="restaurant-reviews-panel__toolbar">
        <span>{statusSummary}</span>
        <label>
          <span className="sr-only">留言排序</span>
          <select value={sort} onChange={(event) => setSort(event.target.value as ReviewSort)}>
            {(Object.keys(sortLabels) as ReviewSort[]).map((value) => (
              <option value={value} key={value}>
                {sortLabels[value]}
              </option>
            ))}
          </select>
          <IconChevronDown aria-hidden="true" />
        </label>
        <div className="restaurant-reviews-panel__filters" aria-label="留言狀態篩選">
          {statusFilters.map((filter) => (
            <button
              type="button"
              key={filter.value}
              className={status === filter.value ? "is-active" : undefined}
              onClick={() => setStatus(filter.value)}
              aria-pressed={status === filter.value}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>
      {success ? (
        <p className="restaurant-reviews-feedback is-success" role="status">
          <IconCheck aria-hidden="true" /> {success}
        </p>
      ) : null}
      {error ? (
        <div className="restaurant-reviews-feedback is-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void load()}>
            重新載入
          </button>
        </div>
      ) : null}
      {loading ? (
        <div className="restaurant-reviews-state" aria-live="polite">
          <IconLoader2 className="is-spinning" aria-hidden="true" />
          <span>正在整理留言…</span>
        </div>
      ) : reviews.length === 0 ? (
        <div className="restaurant-reviews-state is-empty">
          <IconMessageCircle aria-hidden="true" />
          <strong>還沒有留言</strong>
          <span>成為第一個留下實訪紀錄的人。</span>
        </div>
      ) : (
        <div className="restaurant-reviews-list">
          {reviews.map((review) => (
            <ReviewCard
              key={review.id}
              restaurantId={restaurantId}
              review={review}
              availableReasons={reasons}
              onChanged={onChanged}
              onError={setError}
            />
          ))}
        </div>
      )}
    </section>
  );
}
