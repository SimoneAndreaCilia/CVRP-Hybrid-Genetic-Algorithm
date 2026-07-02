"""Prins' Split algorithm for giant tour decomposition.

Converts a permutation of customer IDs (giant tour) into an optimal set
of capacity-feasible CVRP routes via dynamic programming in O(n²) time.

Reference:
    Prins, C. (2004). "A simple and effective evolutionary algorithm for
    the vehicle routing problem." *Computers & Operations Research*, 31(12).
"""

from __future__ import annotations

import numpy as np

from src.models import Instance, Solution


def split(giant_tour: list[int], instance: Instance) -> Solution:
    """Split a giant tour into optimal capacity-feasible routes.

    Uses Bellman-style DP on a DAG where arc (i, j) represents a single
    route serving customers ``giant_tour[i], ..., giant_tour[j-1]``.
    The arc exists only if the cumulative demand does not exceed the
    vehicle capacity. The shortest path from node 0 to node n gives
    the optimal partition.

    Args:
        giant_tour: Permutation of 0-indexed customer IDs (excluding depot).
            Length must equal ``instance.num_customers``.
        instance: The CVRP problem instance.

    Returns:
        A ``Solution`` with optimal routes for the given customer ordering,
        along with the total cost and the original giant tour.
    """
    n = len(giant_tour)
    dist = instance.distance_matrix
    demands = instance.demands
    capacity = instance.capacity
    depot = instance.depot

    # V[k] = minimum cost to serve the first k customers in the tour
    cost_to = np.full(n + 1, np.inf, dtype=np.float64)
    cost_to[0] = 0.0

    # pred[k] = start index of the last route in the optimal partition of [0..k)
    pred = np.zeros(n + 1, dtype=np.int32)

    for i in range(n):
        if cost_to[i] == np.inf:
            continue  # Unreachable state (shouldn't happen with valid data)

        load = 0
        route_cost = 0.0

        for j in range(i, n):
            customer_j = giant_tour[j]
            load += int(demands[customer_j])

            if load > capacity:
                break  # Cannot extend route further

            # Incremental route cost computation
            if j == i:
                # First customer: depot → customer → depot
                route_cost = dist[depot][customer_j] + dist[customer_j][depot]
            else:
                # Extend route: remove return-to-depot of previous customer,
                # add edge to new customer, add new return-to-depot
                customer_prev = giant_tour[j - 1]
                route_cost += (
                    -dist[customer_prev][depot]
                    + dist[customer_prev][customer_j]
                    + dist[customer_j][depot]
                )

            total = cost_to[i] + route_cost
            if total < cost_to[j + 1]:
                cost_to[j + 1] = total
                pred[j + 1] = i

    # Backtrack to extract route boundaries
    routes: list[list[int]] = []
    k = n
    while k > 0:
        start = int(pred[k])
        routes.append(giant_tour[start:k])
        k = start
    routes.reverse()

    return Solution(
        routes=routes,
        cost=float(cost_to[n]),
        giant_tour=list(giant_tour),
    )
