"use client";

import { useEffect, useRef } from "react";
import type { Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";

import type { ItineraryStop } from "@/features/itinerary/api/itinerary-api";
import { buildItineraryRouteLine } from "@/features/itinerary/lib/itinerary-storage";

type ItineraryMapProps = {
  latitude: number;
  longitude: number;
  stops: ItineraryMapStop[];
  showRoute?: boolean;
  fitToStopsOnly?: boolean;
  showOriginMarker?: boolean;
};

export type ItineraryMapStop = {
  order: number;
  role: ItineraryStop["role"];
  place: Pick<ItineraryMapPlace, "latitude" | "longitude" | "icon_color">;
};

type ItineraryMapPlace = {
  latitude: number;
  longitude: number;
  icon_color: string;
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

type RouteFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "LineString"; coordinates: Array<[number, number]> };
    properties: Record<string, never>;
  }>;
};

function stopFeatureCollection(stops: ItineraryMapStop[]): PointFeatureCollection {
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

function routeFeatureCollection(stops: ItineraryMapStop[]): RouteFeatureCollection {
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: buildItineraryRouteLine(stops.map((stop) => stop.place)),
        },
        properties: {},
      },
    ],
  };
}

export function ItineraryMap({
  latitude,
  longitude,
  stops,
  showRoute = true,
  fitToStopsOnly = false,
  showOriginMarker = true,
}: ItineraryMapProps) {
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
      if (showOriginMarker) {
        originMarker = new maplibregl.Marker({ color: "#142B32" })
          .setLngLat([longitude, latitude])
          .setPopup(new maplibregl.Popup({ offset: 18 }).setText("目前位置／搜尋中心"))
          .addTo(map);
      }

      if (stops.length) {
        const firstStop = stops[0];
        const bounds =
          fitToStopsOnly && firstStop
            ? new maplibregl.LngLatBounds(
                [firstStop.place.longitude, firstStop.place.latitude],
                [firstStop.place.longitude, firstStop.place.latitude],
              )
            : new maplibregl.LngLatBounds([longitude, latitude], [longitude, latitude]);
        stops
          .slice(fitToStopsOnly ? 1 : 0)
          .forEach((stop) => bounds.extend([stop.place.longitude, stop.place.latitude]));
        map.fitBounds(bounds, { padding: 72, maxZoom: 14, duration: 0 });
      }

      map.on("load", () => {
        if (!map) return;
        if (showRoute && stops.length > 1) {
          map.addSource("itinerary-route", {
            type: "geojson",
            data: routeFeatureCollection(stops),
          });
          map.addLayer({
            id: "itinerary-route-line",
            type: "line",
            source: "itinerary-route",
            paint: {
              "line-color": "#d96c4f",
              "line-width": 4,
              "line-opacity": 0.82,
              "line-dasharray": [1, 1.2],
            },
            layout: { "line-cap": "round", "line-join": "round" },
          });
        }
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
  }, [fitToStopsOnly, latitude, longitude, showOriginMarker, showRoute, stops]);

  return <div ref={containerRef} className="itinerary-map" aria-label="旅遊行程地圖" />;
}
