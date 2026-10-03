"use client";

import { useEffect, useRef } from "react";
import type { Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";

import type { ItineraryStop } from "@/features/itinerary/api/itinerary-api";

type ItineraryMapProps = {
  latitude: number;
  longitude: number;
  stops: ItineraryStop[];
};

type ItineraryPointProperties = {
  order: number;
  role: ItineraryStop["role"];
  color: string;
};

const mapStyle =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron";

type PointFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: ItineraryPointProperties;
  }>;
};

function stopFeatureCollection(stops: ItineraryStop[]): PointFeatureCollection {
  return {
    type: "FeatureCollection",
    features: stops.map((stop) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [stop.place.longitude, stop.place.latitude],
      },
      properties: {
        order: stop.order,
        role: stop.role,
        color: stop.place.icon_color,
      } satisfies ItineraryPointProperties,
    })),
  };
}

export function ItineraryMap({ latitude, longitude, stops }: ItineraryMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let disposed = false;
    let map: MapLibreMap | null = null;
    let originMarker: MapLibreMarker | null = null;

    async function initializeMap() {
      const maplibregl = await import("maplibre-gl");
      if (disposed || !containerRef.current) return;
      maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
      map = new maplibregl.Map({
        container: containerRef.current,
        style: mapStyle,
        center: [longitude, latitude],
        zoom: stops.length ? 11 : 13,
        attributionControl: false,
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      originMarker = new maplibregl.Marker({ color: "#142B32" })
        .setLngLat([longitude, latitude])
        .setPopup(new maplibregl.Popup({ offset: 18 }).setText("目前位置／搜尋中心"))
        .addTo(map);

      map.on("load", () => {
        if (!map) return;
        map.addSource("itinerary-stops", {
          type: "geojson",
          data: stopFeatureCollection(stops),
        });
        map.addLayer({
          id: "itinerary-stop-circles",
          type: "circle",
          source: "itinerary-stops",
          paint: {
            "circle-color": ["get", "color"],
            "circle-radius": 12,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 3,
          },
        });
        map.addLayer({
          id: "itinerary-stop-labels",
          type: "symbol",
          source: "itinerary-stops",
          layout: {
            "text-field": ["to-string", ["get", "order"]],
            "text-size": 12,
          },
          paint: { "text-color": "#ffffff" },
        });
      });
    }

    void initializeMap();

    return () => {
      disposed = true;
      originMarker?.remove();
      map?.remove();
    };
  }, [latitude, longitude, stops]);

  return <div ref={containerRef} className="itinerary-map" aria-label="旅遊行程地圖" />;
}
