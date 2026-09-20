"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";

type CoordinatePickerProps = {
  latitude: number | null;
  longitude: number | null;
  onChange: (latitude: number, longitude: number) => void | Promise<void>;
};

const taipeiCenter: [number, number] = [121.5654, 25.033];

export function CoordinatePicker({ latitude, longitude, onChange }: CoordinatePickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<MapLibreMarker | null>(null);
  const onChangeRef = useRef(onChange);
  const initialCoordinatesRef = useRef({ latitude, longitude });
  const [mapStatus, setMapStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    let disposed = false;

    async function initializeMap() {
      if (!containerRef.current || mapRef.current) return;
      const maplibregl = await import("maplibre-gl");
      if (disposed || !containerRef.current) return;

      // Next.js/Turbopack needs an explicit public worker for MapLibre GL JS v6.
      // Next.js/Turbopack 需要明確指定 MapLibre v6 的公開 worker 檔案。
      maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

      const initialCoordinates = initialCoordinatesRef.current;
      const initialCenter: [number, number] =
        initialCoordinates.latitude !== null && initialCoordinates.longitude !== null
          ? [initialCoordinates.longitude, initialCoordinates.latitude]
          : taipeiCenter;
      const map = new maplibregl.Map({
        container: containerRef.current,
        style:
          process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron",
        center: initialCenter,
        zoom: initialCoordinates.latitude !== null ? 15 : 11,
        pitch: 0,
        bearing: 0,
        maxPitch: 0,
        dragRotate: false,
        touchPitch: false,
        attributionControl: { compact: true },
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      map.once("load", () => setMapStatus("ready"));
      map.on("error", () => setMapStatus("error"));
      map.on("click", (event) => {
        onChangeRef.current(event.lngLat.lat, event.lngLat.lng);
      });
      mapRef.current = map;
    }

    void initializeMap();
    return () => {
      disposed = true;
      markerRef.current?.remove();
      mapRef.current?.remove();
      markerRef.current = null;
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    async function synchronizeMarker() {
      const map = mapRef.current;
      if (!map || latitude === null || longitude === null) return;
      const maplibregl = await import("maplibre-gl");
      if (!markerRef.current) {
        markerRef.current = new maplibregl.Marker({ color: "#F26B4F", draggable: true })
          .setLngLat([longitude, latitude])
          .addTo(map);
        markerRef.current.on("dragend", () => {
          const position = markerRef.current?.getLngLat();
          if (position) onChangeRef.current(position.lat, position.lng);
        });
      } else {
        markerRef.current.setLngLat([longitude, latitude]);
      }
      // Recenter the map after address geocoding so a distant marker is not left outside the viewport.
      // 地址定位到較遠位置時，重新置中地圖，避免圖釘更新但仍在視野外。
      if (map.loaded()) {
        map.easeTo({
          center: [longitude, latitude],
          zoom: Math.max(map.getZoom(), 15),
          duration: 500,
        });
      }
    }
    void synchronizeMarker();
  }, [latitude, longitude]);

  return (
    <div className="coordinate-picker">
      <div ref={containerRef} className="coordinate-picker__map" aria-label="店家座標地圖" />
      {mapStatus === "error" ? (
        <p className="coordinate-picker__error" role="alert">
          地圖底圖載入失敗，請稍後重試；仍可嘗試點擊地圖建立座標。
        </p>
      ) : null}
      <p className="coordinate-picker__hint">
        <IconMapPin />
        點擊地圖建立圖釘，或拖曳圖釘微調位置。
      </p>
    </div>
  );
}

function IconMapPin() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}
