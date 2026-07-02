"""Genetic operators for the Hybrid Genetic Algorithm.

Provides tournament selection, OX1 crossover, and three mutation
operators (swap, inversion, insertion) designed for permutation
(giant tour) chromosomes.
"""

from __future__ import annotations

import numpy as np

from src.models import Solution


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def tournament_selection(
    population: list[Solution],
    rng: np.random.Generator,
    tournament_size: int = 2,
) -> Solution:
    """Select an individual via tournament selection.

    Picks ``tournament_size`` individuals uniformly at random (without
    replacement) and returns the one with the lowest cost.

    Args:
        population: Current population of solutions.
        rng: Numpy random generator for reproducibility.
        tournament_size: Number of candidates per tournament.

    Returns:
        The tournament winner (lowest cost among candidates).
    """
    indices = rng.choice(len(population), size=tournament_size, replace=False)
    return min((population[i] for i in indices), key=lambda s: s.cost)


# ---------------------------------------------------------------------------
# Crossover
# ---------------------------------------------------------------------------


def ox1_crossover(
    parent1: Solution,
    parent2: Solution,
    rng: np.random.Generator,
) -> list[int]:
    """Order Crossover (OX1) on giant tour chromosomes.

    1. Select a random substring from Parent 1 and copy it to offspring.
    2. Fill remaining positions with genes from Parent 2, preserving
       their relative order and skipping genes already present.

    Preserves relative ordering (adjacency information), which is
    critical for TSP/VRP permutation problems.

    Args:
        parent1: First parent solution.
        parent2: Second parent solution.
        rng: Numpy random generator.

    Returns:
        Offspring giant tour as a list of customer IDs.
    """
    tour1 = parent1.giant_tour
    tour2 = parent2.giant_tour
    n = len(tour1)

    # Random substring boundaries [start, end] inclusive
    positions = sorted(rng.choice(n, size=2, replace=False))
    start, end = int(positions[0]), int(positions[1])

    # Copy substring from parent 1
    offspring: list[int] = [0] * n
    offspring[start : end + 1] = tour1[start : end + 1]
    selected: set[int] = set(tour1[start : end + 1])

    # Fill remaining positions with genes from parent 2 in order,
    # starting from the position after the substring end (wrapping)
    fill_pos = (end + 1) % n
    for gene in tour2[end + 1 :] + tour2[: end + 1]:
        if gene not in selected:
            offspring[fill_pos] = gene
            fill_pos = (fill_pos + 1) % n

    return offspring


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def swap_mutation(tour: list[int], rng: np.random.Generator) -> list[int]:
    """Swap two random positions in the giant tour.

    Args:
        tour: Input permutation.
        rng: Numpy random generator.

    Returns:
        New permutation with two positions swapped.
    """
    result = list(tour)
    n = len(result)
    i, j = rng.choice(n, size=2, replace=False)
    result[i], result[j] = result[j], result[i]
    return result


def inversion_mutation(tour: list[int], rng: np.random.Generator) -> list[int]:
    """Reverse a random sub-sequence (2-opt style mutation).

    Args:
        tour: Input permutation.
        rng: Numpy random generator.

    Returns:
        New permutation with a reversed segment.
    """
    result = list(tour)
    n = len(result)
    positions = sorted(rng.choice(n, size=2, replace=False))
    i, j = int(positions[0]), int(positions[1])
    result[i : j + 1] = result[i : j + 1][::-1]
    return result


def insertion_mutation(tour: list[int], rng: np.random.Generator) -> list[int]:
    """Remove a gene and re-insert it at a random position.

    Args:
        tour: Input permutation.
        rng: Numpy random generator.

    Returns:
        New permutation with one gene relocated.
    """
    result = list(tour)
    n = len(result)
    i = int(rng.integers(n))
    gene = result.pop(i)
    j = int(rng.integers(len(result) + 1))
    result.insert(j, gene)
    return result


def mutate(
    tour: list[int],
    rng: np.random.Generator,
    p_swap: float = 0.15,
    p_inversion: float = 0.15,
    p_insertion: float = 0.10,
) -> list[int]:
    """Apply mutation operators independently with given probabilities.

    Each mutation is applied independently, so an offspring may receive
    0, 1, 2, or all 3 mutations in a single call.

    Args:
        tour: Input giant tour permutation.
        rng: Numpy random generator.
        p_swap: Probability of swap mutation.
        p_inversion: Probability of inversion mutation.
        p_insertion: Probability of insertion mutation.

    Returns:
        Mutated giant tour (may be identical to input if no mutation triggered).
    """
    if rng.random() < p_swap:
        tour = swap_mutation(tour, rng)
    if rng.random() < p_inversion:
        tour = inversion_mutation(tour, rng)
    if rng.random() < p_insertion:
        tour = insertion_mutation(tour, rng)
    return tour
