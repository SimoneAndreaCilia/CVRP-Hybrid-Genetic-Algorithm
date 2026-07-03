"""Core data models for the CVRP Hybrid Genetic Algorithm solver.

Defines the immutable problem instance, mutable solution representation,
fitness evaluation tracker, and algorithm hyperparameter configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from numpy.typing import NDArray


class BudgetExhausted(Exception):
    """Raised when the fitness evaluation budget is exhausted.

    This exception propagates up through the call stack to cleanly
    terminate the HGA run when the FE limit is reached.
    """

    pass


@dataclass
class Instance:
    """Immutable CVRP problem instance parsed from a TSPLIB .vrp file.

    Attributes:
        name: Instance identifier (e.g., "A-n45-k7").
        dimension: Total number of nodes (depot + customers).
        capacity: Maximum vehicle capacity.
        depot: 0-indexed depot node ID.
        coords: Node coordinates, shape (dimension, 2).
        demands: Node demands, shape (dimension,). Depot demand is 0.
        distance_matrix: Precomputed Euclidean distances, shape (dimension, dimension).
    """

    name: str
    dimension: int
    capacity: int
    depot: int
    coords: NDArray[np.float64]
    demands: NDArray[np.int32]
    distance_matrix: NDArray[np.float64]

    @property
    def num_customers(self) -> int:
        """Number of customer nodes (excluding depot)."""
        return self.dimension - 1

    @property
    def customers(self) -> list[int]:
        """List of 0-indexed customer node IDs."""
        return list(range(1, self.dimension))


@dataclass
class Solution:
    """A CVRP solution consisting of vehicle routes.

    Attributes:
        routes: List of routes, each a list of 0-indexed customer node IDs.
            Routes do NOT include the depot; it is implicit at start and end.
        cost: Total travel distance across all routes.
        giant_tour: The chromosome (permutation of customer IDs) that
            produced this solution via the Split algorithm.
    """

    routes: list[list[int]]
    cost: float
    giant_tour: list[int] = field(default_factory=list)

    def is_feasible(self, instance: Instance) -> bool:
        """Verify that all CVRP constraints are satisfied.

        Checks:
            - Every customer is visited exactly once.
            - No route exceeds vehicle capacity.

        Args:
            instance: The problem instance to validate against.

        Returns:
            True if the solution is feasible, False otherwise.
        """
        visited: set[int] = set()
        for route in self.routes:
            route_demand = sum(int(instance.demands[c]) for c in route)
            if route_demand > instance.capacity:
                return False
            for customer in route:
                if customer in visited:
                    return False
                visited.add(customer)
        return visited == set(instance.customers)

    @property
    def num_visited(self) -> int:
        """Total number of customers visited across all routes."""
        return sum(len(route) for route in self.routes)


class FitnessTracker:
    """Centralized, deterministic fitness evaluation counter.

    Injected into ALL algorithm components. Every evaluation of a
    solution's cost (including local search neighbor deltas) must call
    ``record()``. When the FE budget is exhausted, ``BudgetExhausted``
    is raised and propagates up to terminate the run.

    The convergence log samples the best-known cost at regular intervals
    for smooth plotting.

    Attributes:
        max_fe: Maximum allowed fitness evaluations.
        current_fe: Running count of evaluations performed.
        best_cost: Best (lowest) cost observed so far.
        best_fe: FE number at which the best cost was found.
        convergence_log: List of (fe, best_cost) tuples sampled at
            ``log_interval`` intervals.
    """

    def __init__(self, max_fe: int = 350_000, log_interval: int = 500) -> None:
        """Initialize the tracker.

        Args:
            max_fe: Strict upper bound on fitness evaluations.
            log_interval: FE interval for convergence log sampling.
        """
        self.max_fe: int = max_fe
        self.log_interval: int = log_interval
        self.current_fe: int = 0
        self.best_cost: float = float("inf")
        self.best_fe: int = 0
        self.convergence_log: list[tuple[int, float]] = []
        self._next_log: int = 1  # Log the very first FE

    def record(self, cost: float) -> None:
        """Record one fitness evaluation.

        Args:
            cost: The cost of the evaluated solution.

        Raises:
            BudgetExhausted: When ``current_fe >= max_fe``.
        """
        self.current_fe += 1

        if cost < self.best_cost:
            self.best_cost = cost
            self.best_fe = self.current_fe

        # Periodic convergence logging
        if self.current_fe >= self._next_log:
            self.convergence_log.append((self.current_fe, self.best_cost))
            self._next_log = self.current_fe + self.log_interval

        if self.current_fe >= self.max_fe:
            raise BudgetExhausted(
                f"FE budget of {self.max_fe} exhausted at FE={self.current_fe}"
            )

    @property
    def budget_remaining(self) -> bool:
        """True if at least one fitness evaluation remains."""
        return self.current_fe < self.max_fe


@dataclass
class HGAConfig:
    """Hyperparameters for the Hybrid Genetic Algorithm.

    Attributes:
        pop_size: Population size (μ).
        offspring_size: Offspring per generation (λ).
        p_crossover: Probability of applying OX1 crossover.
        tournament_size: Number of candidates in tournament selection.
        nn_fraction: Fraction of initial population seeded with
            Nearest Neighbor heuristic (rest are random).
        p_swap: Probability of swap mutation.
        p_inversion: Probability of inversion (2-opt) mutation.
        p_insertion: Probability of insertion (or-opt) mutation.
    """

    pop_size: int = 50
    offspring_size: int = 25
    p_crossover: float = 0.85
    tournament_size: int = 2
    nn_fraction: float = 0.4
    p_swap: float = 0.15
    p_inversion: float = 0.15
    p_insertion: float = 0.10
    use_local_search: bool = True
