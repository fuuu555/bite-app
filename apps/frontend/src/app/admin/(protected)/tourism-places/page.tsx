"use client";

import { useCallback, useState } from "react";

import { TourismImportPanel } from "@/features/admin/components/tourism-import-panel";
import { TourismPlaceManager } from "@/features/admin/components/tourism-place-manager";

export default function TourismPlacesPage() {
  const [refreshVersion, setRefreshVersion] = useState(0);
  const refreshTourismPlaces = useCallback(() => {
    setRefreshVersion((version) => version + 1);
  }, []);

  return (
    <main className="admin-page">
      <header className="admin-page__header">
        <div>
          <h1>觀光署資料店家</h1>
          <p>管理官方觀光資料的地圖顯示內容，餐飲資料也可以轉成 BiteMap 店家。</p>
        </div>
      </header>
      <TourismImportPanel onImportCompleted={refreshTourismPlaces} />
      <TourismPlaceManager refreshVersion={refreshVersion} />
    </main>
  );
}
