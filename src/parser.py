"""TSPLIB .vrp file format parser.

Reads the standard TSPLIB sections (NODE_COORD_SECTION, DEMAND_SECTION,
DEPOT_SECTION) and constructs an ``Instance`` object with a precomputed
distance matrix.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.distance import compute_distance_matrix
from src.models import Instance


def parse_vrp(filepath: str | Path) -> Instance:
    """Parse a TSPLIB ``.vrp`` file into an ``Instance``.

    Handles the standard CVRP format with EUC_2D distances. Node IDs
    in the file are 1-indexed; they are converted to 0-indexed internally.

    Args:
        filepath: Path to the ``.vrp`` file.

    Returns:
        A fully constructed ``Instance`` with precomputed distance matrix.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required sections are missing or malformed.
    """
    filepath = Path(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    name: str = ""
    dimension: int = 0
    capacity: int = 0
    raw_coords: list[tuple[float, float]] = []
    raw_demands: list[int] = []
    depot: int = 0  # 0-indexed

    section: str | None = None

    for line in lines:
        line = line.strip()
        if not line or line == "EOF":
            continue

        # Detect section headers
        if line.startswith("NODE_COORD_SECTION"):
            section = "coords"
            continue
        elif line.startswith("DEMAND_SECTION"):
            section = "demands"
            continue
        elif line.startswith("DEPOT_SECTION"):
            section = "depot"
            continue

        # Parse header key-value pairs (only outside data sections)
        if section is None and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().upper()
            value = value.strip()
            if key == "NAME":
                name = value
            elif key == "DIMENSION":
                dimension = int(value)
            elif key == "CAPACITY":
                capacity = int(value)
            # TYPE, EDGE_WEIGHT_TYPE, COMMENT are informational only
            continue

        # Parse section data
        if section == "coords":
            parts = line.split()
            raw_coords.append((float(parts[1]), float(parts[2])))

        elif section == "demands":
            parts = line.split()
            raw_demands.append(int(parts[1]))

        elif section == "depot":
            val = int(line.split()[0])
            if val != -1:
                depot = val - 1  # Convert 1-indexed → 0-indexed

    # Validate parsed data
    if dimension == 0:
        raise ValueError(f"DIMENSION not found in {filepath}")
    if len(raw_coords) != dimension:
        raise ValueError(
            f"Expected {dimension} coordinates, got {len(raw_coords)}"
        )
    if len(raw_demands) != dimension:
        raise ValueError(
            f"Expected {dimension} demands, got {len(raw_demands)}"
        )

    coords = np.array(raw_coords, dtype=np.float64)
    demands = np.array(raw_demands, dtype=np.int32)
    distance_matrix = compute_distance_matrix(coords)

    return Instance(
        name=name,
        dimension=dimension,
        capacity=capacity,
        depot=depot,
        coords=coords,
        demands=demands,
        distance_matrix=distance_matrix,
    )
