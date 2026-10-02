"use client";

import { IconArrowRight, IconTrash } from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { AppConfirmDialog } from "@/shared/ui/app-confirm-dialog";
import { clearMealDraft, useMealDraft } from "@/features/meals/utils/meal-draft";

export function MealDraftBar() {
  const pathname = usePathname();
  const draft = useMealDraft();
  const [confirmOpen, setConfirmOpen] = useState(false);

  if (!draft || pathname.startsWith("/meals")) return null;

  const abandonDraft = () => {
    setConfirmOpen(true);
  };

  return (
    <>
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
      <AppConfirmDialog
        open={confirmOpen}
        title="放棄約飯草稿"
        message="已填內容與候選餐廳都會清除，確定要放棄嗎？"
        confirmLabel="放棄草稿"
        danger
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          clearMealDraft();
          setConfirmOpen(false);
        }}
      />
    </>
  );
}
