"""Local search operators for CVRP solution improvement.

Implements three neighborhood structures applied in first-improvement
strategy:
    1. **2-opt (intra-route):** Reverse a segment within a single route.
    2. **Relocate (inter-route):** Move a customer to another route.
    3. **Exchange (inter-route):** Swap customers between two routes.

Each neighbor evaluation counts as 1 fitness evaluation (FE). The
``BudgetExhausted`` exception propagates up when the FE budget is hit.
"""

from __future__ import annotations

from src.models import BudgetExhausted, FitnessTracker, Instance, Solution


# ---------------------------------------------------------------------------
# Intra-route: 2-opt
# ---------------------------------------------------------------------------


def _two_opt_intra(
    routes: list[list[int]],
    current_cost: float,
    instance: Instance,
    tracker: FitnessTracker,
) -> float:
    """Apply 2-opt to each route until intra-route local optimum.

    Uses first-improvement strategy: as soon as an improving reversal
    is found, apply it and restart scanning the same route.

    Args:
        routes: Mutable list of routes (modified in place).
        current_cost: Current total solution cost.
        instance: The CVRP problem instance.
        tracker: Fitness evaluation tracker.

    Returns:
        Updated total cost after all 2-opt improvements.
    """
    dist = instance.distance_matrix
    depot = instance.depot

    for ri in range(len(routes)):
        route = routes[ri]
        improved = True

        while improved:
            improved = False
            n = len(route)
            if n < 2:
                break

            for i in range(n - 1):
                for j in range(i + 1, n):
                    # Nodes adjacent to the reversed segment
                    prev_i = depot if i == 0 else route[i - 1]
                    next_j = depot if j == n - 1 else route[j + 1]

                    # Delta = (new edges) - (old edges)
                    delta = (
                        dist[prev_i][route[j]]
                        + dist[route[i]][next_j]
                        - dist[prev_i][route[i]]
                        - dist[route[j]][next_j]
                    )

                    neighbor_cost = current_cost + delta
                    tracker.record(neighbor_cost)  # +1 FE

                    if delta < -1e-10:
                        route[i : j + 1] = route[i : j + 1][::-1]
                        current_cost = neighbor_cost
                        improved = True
                        break  # Restart scanning this route

                if improved:
                    break

    return current_cost


# ---------------------------------------------------------------------------
# Inter-route: Relocate
# ---------------------------------------------------------------------------


def _relocate_inter(
    routes: list[list[int]],
    current_cost: float,
    instance: Instance,
    tracker: FitnessTracker,
) -> float:
    """Move a customer from one route to the best insertion in another.

    Uses first-improvement strategy with full restart after each
    improving move. Empty routes are cleaned up between restarts.

    Args:
        routes: Mutable list of routes (modified in place).
        current_cost: Current total solution cost.
        instance: The CVRP problem instance.
        tracker: Fitness evaluation tracker.

    Returns:
        Updated total cost after all relocate improvements.
    """
    dist = instance.distance_matrix
    depot = instance.depot
    demands = instance.demands
    capacity = instance.capacity

    improved = True
    while improved:
        improved = False

        # Clean up empty routes
        routes[:] = [r for r in routes if r]

        # Precompute route demands
        route_demands = [
            sum(int(demands[c]) for c in r) for r in routes
        ]
        num_routes = len(routes)

        for r1 in range(num_routes):
            for pos in range(len(routes[r1])):
                customer = routes[r1][pos]
                c_demand = int(demands[customer])
                route1 = routes[r1]

                # Cost of removing customer from route r1
                prev_c = depot if pos == 0 else route1[pos - 1]
                next_c = (
                    depot if pos == len(route1) - 1 else route1[pos + 1]
                )
                removal_saving = (
                    dist[prev_c][customer]
                    + dist[customer][next_c]
                    - dist[prev_c][next_c]
                )

                for r2 in range(num_routes):
                    if r1 == r2:
                        continue
                    if route_demands[r2] + c_demand > capacity:
                        continue

                    route2 = routes[r2]

                    # Try inserting at each position in route2
                    for ins in range(len(route2) + 1):
                        prev_ins = depot if ins == 0 else route2[ins - 1]
                        next_ins = (
                            depot if ins == len(route2) else route2[ins]
                        )

                        insertion_cost = (
                            dist[prev_ins][customer]
                            + dist[customer][next_ins]
                            - dist[prev_ins][next_ins]
                        )

                        delta = insertion_cost - removal_saving
                        neighbor_cost = current_cost + delta
                        tracker.record(neighbor_cost)  # +1 FE

                        if delta < -1e-10:
                            # Apply: remove from r1, insert into r2
                            routes[r1].pop(pos)
                            route_demands[r1] -= c_demand
                            routes[r2].insert(ins, customer)
                            route_demands[r2] += c_demand
                            current_cost = neighbor_cost
                            improved = True
                            break

                    if improved:
                        break
                if improved:
                    break
            if improved:
                break

    return current_cost


# ---------------------------------------------------------------------------
# Inter-route: Exchange
# ---------------------------------------------------------------------------


def _exchange_inter(
    routes: list[list[int]],
    current_cost: float,
    instance: Instance,
    tracker: FitnessTracker,
) -> float:
    """Swap a customer from one route with a customer from another.

    Uses first-improvement strategy with full restart after each
    improving swap. Capacity constraints are checked before evaluation.

    Args:
        routes: Mutable list of routes (modified in place).
        current_cost: Current total solution cost.
        instance: The CVRP problem instance.
        tracker: Fitness evaluation tracker.

    Returns:
        Updated total cost after all exchange improvements.
    """
    dist = instance.distance_matrix
    depot = instance.depot
    demands = instance.demands
    capacity = instance.capacity

    improved = True
    while improved:
        improved = False

        # Clean up empty routes
        routes[:] = [r for r in routes if r]

        route_demands = [
            sum(int(demands[c]) for c in r) for r in routes
        ]
        num_routes = len(routes)

        for r1 in range(num_routes - 1):
            for i in range(len(routes[r1])):
                c1 = routes[r1][i]
                d1 = int(demands[c1])

                for r2 in range(r1 + 1, num_routes):
                    for j in range(len(routes[r2])):
                        c2 = routes[r2][j]
                        d2 = int(demands[c2])

                        # Capacity feasibility check
                        if route_demands[r1] - d1 + d2 > capacity:
                            continue
                        if route_demands[r2] - d2 + d1 > capacity:
                            continue

                        # Compute delta for swapping c1 ↔ c2
                        route1 = routes[r1]
                        route2 = routes[r2]

                        prev_c1 = depot if i == 0 else route1[i - 1]
                        next_c1 = (
                            depot
                            if i == len(route1) - 1
                            else route1[i + 1]
                        )
                        prev_c2 = depot if j == 0 else route2[j - 1]
                        next_c2 = (
                            depot
                            if j == len(route2) - 1
                            else route2[j + 1]
                        )

                        old_edges = (
                            dist[prev_c1][c1]
                            + dist[c1][next_c1]
                            + dist[prev_c2][c2]
                            + dist[c2][next_c2]
                        )
                        new_edges = (
                            dist[prev_c1][c2]
                            + dist[c2][next_c1]
                            + dist[prev_c2][c1]
                            + dist[c1][next_c2]
                        )
                        delta = new_edges - old_edges

                        neighbor_cost = current_cost + delta
                        tracker.record(neighbor_cost)  # +1 FE

                        if delta < -1e-10:
                            routes[r1][i] = c2
                            routes[r2][j] = c1
                            route_demands[r1] += d2 - d1
                            route_demands[r2] += d1 - d2
                            current_cost = neighbor_cost
                            improved = True
                            break

                    if improved:
                        break
                if improved:
                    break
            if improved:
                break

    return current_cost


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def local_search(
    solution: Solution,
    instance: Instance,
    tracker: FitnessTracker,
) -> Solution:
    """Apply full local search: 2-opt → Relocate → Exchange.

    Runs the three neighborhoods in sequence, looping until no
    neighborhood finds an improvement (composite local optimum).
    ``BudgetExhausted`` exceptions from the tracker are caught so
    that partial improvements are preserved, then re-raised.

    Args:
        solution: Input solution to improve.
        instance: The CVRP problem instance.
        tracker: Fitness evaluation tracker.

    Returns:
        Locally optimal solution (or partially improved if budget hit).

    Raises:
        BudgetExhausted: Re-raised after saving the improved solution.
    """
    # Deep-copy routes so the original solution is not mutated
    routes = [list(r) for r in solution.routes]
    current_cost = solution.cost
    budget_hit = False

    try:
        overall_improved = True
        while overall_improved:
            overall_improved = False

            old_cost = current_cost
            current_cost = _two_opt_intra(routes, current_cost, instance, tracker)
            if current_cost < old_cost - 1e-10:
                overall_improved = True

            old_cost = current_cost
            current_cost = _relocate_inter(routes, current_cost, instance, tracker)
            if current_cost < old_cost - 1e-10:
                overall_improved = True

            old_cost = current_cost
            current_cost = _exchange_inter(routes, current_cost, instance, tracker)
            if current_cost < old_cost - 1e-10:
                overall_improved = True

    except BudgetExhausted:
        budget_hit = True

    # Build result with cleaned-up routes
    clean_routes = [r for r in routes if r]
    result = Solution(
        routes=clean_routes,
        cost=current_cost,
        giant_tour=[customer for route in clean_routes for customer in route],
    )

    if budget_hit:
        raise BudgetExhausted(
            f"Budget exhausted during local search at cost={current_cost:.2f}"
        )

    return result
