"""Create configurable in-boundary sampling points for future coverage discovery."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import geopandas as gpd
import numpy as np
from shapely.geometry import shape

from app.services.study_area_service import (
    STUDY_AREA_ID,
    contains_point,
    get_study_area_geometry,
)


def generate_sampling_points(spacing_meters: float) -> tuple[list[dict[str, Any]], int]:
    """Build a meter-spaced point grid and retain only points inside the official area."""
    if spacing_meters <= 0:
        raise ValueError("spacing_meters must be greater than zero.")

    # GeoJSON coordinates are WGS84 longitude/latitude. Project only for meter spacing.
    area_wgs84 = gpd.GeoDataFrame(geometry=[shape(get_study_area_geometry())], crs="EPSG:4326")
    local_crs = area_wgs84.estimate_utm_crs()
    if local_crs is None:
        raise ValueError("A suitable local projected CRS could not be determined.")
    area_projected = area_wgs84.to_crs(local_crs)
    min_x, min_y, max_x, max_y = area_projected.total_bounds
    x_values = np.arange(min_x, max_x + spacing_meters, spacing_meters)
    y_values = np.arange(min_y, max_y + spacing_meters, spacing_meters)
    x_grid, y_grid = np.meshgrid(x_values, y_values)
    candidates = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(x_grid.ravel(), y_grid.ravel()), crs=local_crs
    )
    # ``within`` excludes the boundary, meeting the requirement for points inside it.
    area_shape = area_projected.geometry.iloc[0]
    inside = candidates[candidates.geometry.within(area_shape)].to_crs("EPSG:4326")

    documents: list[dict[str, Any]] = []
    for point in inside.geometry:
        latitude, longitude = float(point.y), float(point.x)
        # A second validation uses the official source geometry in its native CRS.
        if contains_point(latitude, longitude):
            documents.append({
                "sample_id": f"sample_{uuid4().hex}",
                "latitude": latitude,
                "longitude": longitude,
                "location": {"type": "Point", "coordinates": [longitude, latitude]},
                "study_area_id": STUDY_AREA_ID,
                "status": "pending_coverage_discovery",
            })
    # Candidates outside the polygon are only an internal calculation, not samples.
    return documents, len(documents)
