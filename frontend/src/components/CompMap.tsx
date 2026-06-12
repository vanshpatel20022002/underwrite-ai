"use client";

import { useEffect, useRef } from "react";
import type { Comp } from "@/lib/api";

interface Props {
  subjectLat?: number;
  subjectLon?: number;
  comps: Comp[];
}

export default function CompMap({ subjectLat, subjectLon, comps }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<import("leaflet").Map | null>(null);

  useEffect(() => {
    if (!mapRef.current || typeof window === "undefined") return;

    let cancelled = false;

    async function initMap() {
      const L = (await import("leaflet")).default;

      if (cancelled || !mapRef.current) return;

      if (mapInstance.current) {
        mapInstance.current.remove();
      }

      const centerLat = subjectLat ?? comps[0]?.latitude ?? 30.27;
      const centerLon = subjectLon ?? comps[0]?.longitude ?? -97.74;

      const map = L.map(mapRef.current).setView([centerLat, centerLon], 12);
      mapInstance.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
      }).addTo(map);

      if (subjectLat && subjectLon) {
        L.circleMarker([subjectLat, subjectLon], {
          radius: 10,
          color: "#3b82f6",
          fillColor: "#3b82f6",
          fillOpacity: 0.8,
        })
          .addTo(map)
          .bindPopup("Subject Property");
      }

      comps.forEach((comp, i) => {
        if (comp.latitude && comp.longitude) {
          L.circleMarker([comp.latitude, comp.longitude], {
            radius: 8,
            color: "#22c55e",
            fillColor: "#22c55e",
            fillOpacity: 0.7,
          })
            .addTo(map)
            .bindPopup(`Comp #${i + 1}: $${comp.sale_price.toLocaleString()}`);
        }
      });
    }

    initMap();

    return () => {
      cancelled = true;
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [subjectLat, subjectLon, comps]);

  return (
    <div
      ref={mapRef}
      style={{ height: "350px", borderRadius: "12px", border: "1px solid var(--border)" }}
    />
  );
}
