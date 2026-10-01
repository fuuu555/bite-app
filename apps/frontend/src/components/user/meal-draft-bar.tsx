"use client";

import { IconArrowRight, IconTrash } from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { clearMealDraft, useMealDraft } from "@/lib/meal-draft";

export function MealDraftBar() {
  const pathname = usePathname();
  const draft = useMealDraft();

  if (!draft || pathname.startsWith("/meals")) return null;

  const abandonDraft = () => {
    if (!window.confirm("確定要放棄這份約飯草稿嗎？已填內容與候選餐廳都會清除。")) return;
    clearMealDraft();
  };

  return (
    <aside className="meal-draft-bar" aria-label="約飯草稿">
      <div>
        <strong>約飯草稿</strong>
        <span>
          {draft.restaurantMode === "vote"
            ? `已選 ${draft.candidates.length} / 3 家候選`
            : draft.candidates[0]?.name || "尚未選擇餐廳"}
        </span>
      </div>
      <nav aria-label="約飯草稿操作">
        <button type="button" onClick={abandonDraft}>
          <IconTrash aria-hidden="true" />
          放棄
        </button>
        <Link href="/meals?compose=1">
          返回填寫
          <IconArrowRight aria-hidden="true" />
        </Link>
      </nav>
    </aside>
  );
}
