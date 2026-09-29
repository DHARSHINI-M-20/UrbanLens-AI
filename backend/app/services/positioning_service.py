"""Modular building positioning using view rays and optional OSM footprints."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from shapely.geometry import LineString, Point, shape
from shapely.ops import nearest_points, transform


class PositioningService:
    """Triangulate camera rays conservatively or approximate a single-view location."""

    def __init__(
        self,
        *,
        ray_search_limit_meters: float = 500.0,
        max_ray_residual_meters: float = 2.0,
    ) -> None:
        if ray_search_limit_meters <= 0:
            raise ValueError("ray_search_limit_meters must be positive.")
        if max_ray_residual_meters < 0:
            raise ValueError("max_ray_residual_meters must be non-negative.")
        self.ray_search_limit_meters = ray_search_limit_meters
        self.max_ray_residual_meters = max_ray_residual_meters

    def position_building(
        self,
        view_observations: Sequence[Mapping[str, Any]],
        *,
        footprints: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        if not view_observations:
            raise ValueError("At least one view observation is required.")
        sources = list(dict.fromkeys(
            str(item.get("source_view_id") or item.get("view_id"))
            for item in view_observations
            if item.get("source_view_id") or item.get("view_id")
        ))
        if len(sources) >= 2:
            return self.triangulate_views(view_observations)

        observation = view_observations[0]
        view_id = str(observation.get("source_view_id") or observation.get("view_id") or "")
        for footprint in footprints:
            result = self._intersect_footprint(observation, footprint, view_id)
            if result is not None:
                return result

        latitude = observation.get("camera_latitude", observation.get("latitude"))
        longitude = observation.get("camera_longitude", observation.get("longitude"))
        if latitude is None or longitude is None:
            raise ValueError("Single-view positioning requires camera coordinates.")
        return {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "building_reference_id": None,
            "positioning_method": "camera_location_approximation",
            "positioning_confidence": None,
            "source_views": [view_id] if view_id else [],
            "review_status": "needs_review",
        }

    def triangulate_views(self, view_observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Intersect forward camera rays; no accuracy is inferred from geometry alone.

        `max_ray_residual_meters` is a consistency gate for the supplied rays, not
        a claim about positional accuracy. Successful coordinates remain
        unvalidated and require review until FarmwiseAI ground truth is available.
        """
        source_views = list(dict.fromkeys(
            str(item.get("source_view_id") or item.get("view_id"))
            for item in view_observations
            if item.get("source_view_id") or item.get("view_id")
        ))
        base = {
            "latitude": None,
            "longitude": None,
            "building_reference_id": self._common_reference_id(view_observations),
            "positioning_confidence": None,
            "positioning_confidence_status": "unavailable",
            "source_views": source_views,
            "review_status": "needs_review",
        }
        if len(source_views) < 2:
            return {
                **base,
                "positioning_method": "unavailable_insufficient_views",
                "positioning_reason": "At least two distinct view rays are required.",
            }

        rays = [
            (observation, self._ray_input(observation))
            for observation in view_observations
        ]
        if any(not ray["ready"] for _, ray in rays) or len(rays) < 2:
            return {
                **base,
                "positioning_method": "unavailable_invalid_view_geometry",
                "positioning_reason": "One or more camera positions or headings are invalid or unavailable.",
            }

        latitudes = [ray["camera_latitude"] for _, ray in rays]
        longitudes = [ray["camera_longitude"] for _, ray in rays]
        origin_latitude = sum(latitudes) / len(latitudes)
        origin_longitude = sum(longitudes) / len(longitudes)
        meters_per_longitude = 111_320 * math.cos(math.radians(origin_latitude))
        if abs(meters_per_longitude) < 1:
            return {
                **base,
                "positioning_method": "unavailable_invalid_view_geometry",
                "positioning_reason": "Camera positions are too close to a pole for the local tangent projection.",
            }

        projected_rays: list[tuple[float, float, float, float, str]] = []
        for observation, ray in rays:
            camera_x = (ray["camera_longitude"] - origin_longitude) * meters_per_longitude
            camera_y = (ray["camera_latitude"] - origin_latitude) * 111_320
            bearing = math.radians(ray["heading_degrees"])
            direction_x = math.sin(bearing)
            direction_y = math.cos(bearing)
            view_id = str(observation.get("source_view_id") or observation.get("view_id"))
            projected_rays.append((camera_x, camera_y, direction_x, direction_y, view_id))

        matrix_xx = matrix_xy = matrix_yy = vector_x = vector_y = 0.0
        for camera_x, camera_y, direction_x, direction_y, _ in projected_rays:
            projection_xx = 1 - direction_x * direction_x
            projection_xy = -direction_x * direction_y
            projection_yy = 1 - direction_y * direction_y
            matrix_xx += projection_xx
            matrix_xy += projection_xy
            matrix_yy += projection_yy
            vector_x += projection_xx * camera_x + projection_xy * camera_y
            vector_y += projection_xy * camera_x + projection_yy * camera_y

        determinant = matrix_xx * matrix_yy - matrix_xy * matrix_xy
        trace = matrix_xx + matrix_yy
        if trace == 0 or determinant <= 1e-10 * trace * trace:
            return {
                **base,
                "positioning_method": "unavailable_parallel_or_degenerate_rays",
                "positioning_reason": "View headings do not provide a stable ray intersection.",
            }

        position_x = (vector_x * matrix_yy - vector_y * matrix_xy) / determinant
        position_y = (matrix_xx * vector_y - matrix_xy * vector_x) / determinant
        residuals: list[float] = []
        for camera_x, camera_y, direction_x, direction_y, _ in projected_rays:
            offset_x, offset_y = position_x - camera_x, position_y - camera_y
            forward_distance = offset_x * direction_x + offset_y * direction_y
            if forward_distance <= 0:
                return {
                    **base,
                    "positioning_method": "unavailable_no_forward_ray_intersection",
                    "positioning_reason": "The calculated location is behind at least one camera ray.",
                }
            residuals.append(abs(offset_x * direction_y - offset_y * direction_x))

        maximum_residual = max(residuals, default=0.0)
        if maximum_residual > self.max_ray_residual_meters:
            return {
                **base,
                "positioning_method": "unavailable_inconsistent_view_geometry",
                "positioning_reason": "Camera rays do not converge within the configured geometric consistency threshold.",
                "max_ray_residual_meters": maximum_residual,
            }

        latitude = origin_latitude + position_y / 111_320
        longitude = origin_longitude + position_x / meters_per_longitude
        return {
            **base,
            "latitude": latitude,
            "longitude": longitude,
            "positioning_method": "multi_view_ray_intersection",
            "positioning_confidence_status": "unvalidated_low",
            "max_ray_residual_meters": maximum_residual,
            "review_status": "needs_review",
        }

    @staticmethod
    def _common_reference_id(observations: Sequence[Mapping[str, Any]]) -> str | None:
        reference_ids = {
            str(item.get("reference_id") or item.get("building_reference_id"))
            for item in observations
            if item.get("reference_id") or item.get("building_reference_id")
        }
        return next(iter(reference_ids)) if len(reference_ids) == 1 else None

    def _ray_input(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        latitude = observation.get("camera_latitude", observation.get("latitude"))
        longitude = observation.get("camera_longitude", observation.get("longitude"))
        heading = observation.get("heading")
        if latitude is None or longitude is None or heading is None:
            return {"view_id": observation.get("source_view_id"), "ready": False}
        try:
            latitude, longitude, heading = float(latitude), float(longitude), float(heading)
        except (TypeError, ValueError):
            return {"view_id": observation.get("source_view_id"), "ready": False}
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or not 0 <= heading <= 360:
            return {"view_id": observation.get("source_view_id"), "ready": False}
        return {
            "view_id": observation.get("source_view_id") or observation.get("view_id"),
            "camera_latitude": latitude,
            "camera_longitude": longitude,
            "heading_degrees": heading,
            "ready": True,
        }

    def _intersect_footprint(
        self,
        observation: Mapping[str, Any],
        footprint: Mapping[str, Any],
        view_id: str,
    ) -> dict[str, Any] | None:
        geometry_data = footprint.get("geometry", footprint)
        if not isinstance(geometry_data, Mapping):
            return None
        try:
            polygon_geo = shape(geometry_data)
            latitude = float(observation.get("camera_latitude", observation.get("latitude")))
            longitude = float(observation.get("camera_longitude", observation.get("longitude")))
            heading = float(observation["heading"])
        except (KeyError, TypeError, ValueError, AttributeError):
            return None
        if polygon_geo.is_empty or polygon_geo.geom_type not in {"Polygon", "MultiPolygon"}:
            return None
        if not 0 <= heading <= 360:
            return None

        meters_per_longitude = 111_320 * math.cos(math.radians(latitude))
        if abs(meters_per_longitude) < 1:
            return None

        def project(lon: float, lat: float, _z: float | None = None):
            return ((lon - longitude) * meters_per_longitude, (lat - latitude) * 111_320)

        def unproject(x: float, y: float, _z: float | None = None):
            return (longitude + x / meters_per_longitude, latitude + y / 111_320)

        polygon = transform(project, polygon_geo)
        radians = math.radians(heading)
        endpoint = Point(
            self.ray_search_limit_meters * math.sin(radians),
            self.ray_search_limit_meters * math.cos(radians),
        )
        ray = LineString([(0.0, 0.0), (endpoint.x, endpoint.y)])
        intersection = ray.intersection(polygon)
        if intersection.is_empty:
            _, nearest_point = nearest_points(ray, polygon.boundary)
            method = "footprint_association_no_ray_intersection"
        else:
            _, nearest_point = nearest_points(Point(0, 0), intersection)
            method = "line_of_sight_footprint_intersection"
        lon, lat = unproject(nearest_point.x, nearest_point.y)
        properties = footprint.get("properties") or {}
        return {
            "latitude": lat,
            "longitude": lon,
            "building_reference_id": footprint.get("reference_id") or properties.get("reference_id") or footprint.get("id"),
            "positioning_method": method,
            "positioning_confidence": None,
            "source_views": [view_id] if view_id else [],
            "review_status": "needs_review",
        }
