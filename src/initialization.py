"""Population initialization strategies for the HGA.

Provides Nearest Neighbor heuristic and random permutation generators
for seeding the initial population with a mix of quality and diversity.
"""

from __future__ import annotations

import numpy as np

from src.models import FitnessTracker, Instance, Solution
from src.split import split


def nearest_neighbor_tour(
    instance: Instance,
    rng: np.random.Generator,
    start: int | None = None,
) -> list[int]:
    """Generate a giant tour using the Nearest Neighbor heuristic.

    Starting from a (possibly random) customer, greedily visit the
    nearest unvisited customer until all are served. Different start
    nodes produce different tours, ensuring diversity.

    Args:
        instance: The CVRP problem instance.
        rng: Numpy random generator for start node selection.
        start: Optional fixed start customer (0-indexed). If None,
            a random customer is chosen.

    Returns:
        Giant tour as a list of 0-indexed customer IDs.
    """
    customers = set(instance.customers)

    if start is None:
        start = int(rng.choice(list(customers)))

    tour: list[int] = [start]
    customers.remove(start)
    current = start

    while customers:
        nearest = min(
            customers, key=lambda c: instance.distance_matrix[current][c]
        )
        tour.append(nearest)
        customers.remove(nearest)
        current = nearest

    return tour


def random_tour(instance: Instance, rng: np.random.Generator) -> list[int]:
    """Generate a random permutation giant tour.

    Args:
        instance: The CVRP problem instance.
        rng: Numpy random generator.

    Returns:
        Uniformly random permutation of 0-indexed customer IDs.
    """
    customers = list(instance.customers)
    rng.shuffle(customers)
    return customers


def initialize_population(
    instance: Instance,
    pop_size: int,
    tracker: FitnessTracker,
    rng: np.random.Generator,
    nn_fraction: float = 0.4,
) -> list[Solution]:
    """Create the initial population using a mix of heuristics.

    The first ``nn_fraction`` of the population is seeded with Nearest
    Neighbor tours (each starting from a different random customer).
    The remainder uses purely random permutations. Each tour is decoded
    via Prins' Split and the resulting solution is evaluated (1 FE each).

    Args:
        instance: The CVRP problem instance.
        pop_size: Target population size (μ).
        tracker: Fitness evaluation tracker.
        rng: Numpy random generator.
        nn_fraction: Fraction of population initialized with NN heuristic.

    Returns:
        List of ``pop_size`` evaluated solutions, sorted by cost.
    """
    population: list[Solution] = []
    nn_count = int(pop_size * nn_fraction)

    for i in range(pop_size):
        if i < nn_count:
            tour = nearest_neighbor_tour(instance, rng)
        else:
            tour = random_tour(instance, rng)

        solution = split(tour, instance)
        tracker.record(solution.cost)  # +1 FE
        population.append(solution)

    population.sort(key=lambda s: s.cost)
    return population
