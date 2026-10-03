"""Deterministic metadata-only provider for clearly labelled local demos."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from shapely.geometry import Point, shape

from app.services.study_area_service import get_study_area_geometry
from app.services.streetview_service import StreetViewProviderError

SIMULATION_LABEL = "SIMULATED TAMIL NADU URBAN DATA — NOT REAL STREET VIEW DATA"
SIMULATION_SOURCE = "SIMULATED_TAMIL_NADU_DATA"


class SimulatedStreetViewProvider:
    """Implements the existing provider contract without network access."""

    name = "simulated"
    source_name = SIMULATION_SOURCE
    is_simulated = True

    def __init__(self, *, dataset_id: str = "tn_study_area_demo_v1") -> None:
        self.dataset_id = dataset_id
        self._panoramas = self._build_panorama_metadata()

    def _build_panorama_metadata(self) -> tuple[dict[str, Any], ...]:
        area = shape(get_study_area_geometry())
        center = area.representative_point()
        min_lon, min_lat, max_lon, max_lat = area.bounds
        groups: list[tuple[float, float, float, float]] = []
        for row in (0.28, 0.5, 0.72):
            for column in (0.25, 0.5, 0.75):
                target_lat = min_lat + (max_lat - min_lat) * row
                target_lon = min_lon + (max_lon - min_lon) * column
                meters_per_lon = 111_320 * max(0.1, __import__("math").cos(__import__("math").radians(target_lat)))
                west = (target_lat, target_lon - 8 / meters_per_lon)
                south = (target_lat - 8 / 111_320, target_lon)
                if not all(area.covers(Point(lon, lat)) for lat, lon in (west, south)):
                    continue
                if any(
                    ((target_lat - prior_lat) * 111_320) ** 2
                    + ((target_lon - prior_lon) * meters_per_lon) ** 2 < 180 ** 2
                    for prior_lat, prior_lon, _, _ in groups
                ):
                    continue
                groups.append((target_lat, target_lon, west[1], south[0]))
                if len(groups) == 3:
                    break
            if len(groups) == 3:
                break
        if not groups:
            groups = [(center.y, center.x, center.x - 0.00007, center.y - 0.00007)]

        panoramas: list[dict[str, Any]] = []
        for group_index, (target_lat, target_lon, west_lon, south_lat) in enumerate(groups, start=1):
            pair = ((target_lat, west_lon, 90.0), (south_lat, target_lon, 0.0))
            for side, (latitude, longitude, heading) in zip(("a", "b"), pair):
                panorama_id = f"{self.dataset_id}_pano_{group_index:02d}{side}"
                panoramas.append({
                    "panorama_id": panorama_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "captured_at": date(2026, 9, 1).isoformat(),
                    "available_headings": [heading],
                    "pitch": 0.0,
                    "field_of_view": 90.0,
                    "quality": {"score": 0.91 - group_index * 0.03},
                    "evidence_reference": f"simulated://panoramas/{panorama_id}",
                    "provider": "simulated",
                    "simulation": True,
                    "group_id": f"sim_group_{group_index:02d}",
                    "dataset_id": self.dataset_id,
                    "source": SIMULATION_LABEL,
                })
        return tuple(panoramas)

    def discover_metadata(self, *, latitude: float, longitude: float, radius_meters: int) -> Mapping[str, Any]:
        candidates = sorted(
            self._panoramas,
            key=lambda item: (item["latitude"] - latitude) ** 2 + (item["longitude"] - longitude) ** 2,
        )
        if not candidates:
            raise StreetViewProviderError("No simulated panorama metadata is available.")
        panorama = candidates[0]
        north_meters = (panorama["latitude"] - latitude) * 111_320
        east_meters = (panorama["longitude"] - longitude) * 111_320
        if (north_meters * north_meters + east_meters * east_meters) ** 0.5 > radius_meters:
            raise StreetViewProviderError("No simulated panorama is available within the requested radius.")
        return dict(panorama)

    def all_metadata(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self._panoramas)

    def group_targets(self) -> dict[str, tuple[float, float]]:
        targets: dict[str, tuple[float, float]] = {}
        for panorama in self._panoramas:
            group_id = str(panorama["group_id"])
            if group_id in targets:
                continue
            member = next(
                item for item in self._panoramas
                if item["group_id"] == group_id and item["available_headings"] == [90.0]
            )
            target_lat = next(
                item["latitude"] for item in self._panoramas
                if item["group_id"] == group_id and item["available_headings"] == [0.0]
            ) + 8 / 111_320
            meters_per_lon = 111_320 * __import__("math").cos(__import__("math").radians(target_lat))
            targets[group_id] = (target_lat, member["longitude"] + 8 / meters_per_lon)
        return targets