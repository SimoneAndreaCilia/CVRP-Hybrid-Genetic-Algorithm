"""Hybrid Genetic Algorithm orchestrator for CVRP.

Manages the evolutionary loop: initialization → [selection → crossover
→ mutation → split → local search → replacement] until FE budget is
exhausted. Uses (μ + λ) elitist replacement with duplicate elimination.
"""

from __future__ import annotations

import numpy as np

from src.initialization import initialize_population
from src.local_search import local_search
from src.models import (
    BudgetExhausted,
    FitnessTracker,
    HGAConfig,
    Instance,
    Solution,
)
from src.operators import mutate, ox1_crossover, tournament_selection
from src.split import split


class HybridGeneticAlgorithm:
    """Hybrid Genetic Algorithm for the Capacitated Vehicle Routing Problem.

    Combines evolutionary search (OX1 crossover, multi-mutation) with
    local search refinement (2-opt, relocate, exchange) on a giant tour
    representation decoded via Prins' Split algorithm.

    Attributes:
        instance: The CVRP problem instance.
        tracker: Fitness evaluation tracker (shared across all components).
        config: Algorithm hyperparameters.
        rng: Seeded numpy random generator for reproducibility.
    """

    def __init__(
        self,
        instance: Instance,
        tracker: FitnessTracker,
        seed: int = 42,
        config: HGAConfig | None = None,
    ) -> None:
        """Initialize the HGA.

        Args:
            instance: The CVRP problem instance to solve.
            tracker: Fitness evaluation tracker with FE budget.
            seed: Random seed for reproducibility.
            config: Optional hyperparameters (defaults to ``HGAConfig()``).
        """
        self.instance = instance
        self.tracker = tracker
        self.config = config or HGAConfig()
        self.rng = np.random.default_rng(seed)

    def run(self) -> Solution:
        """Execute the HGA until the FE budget is exhausted.

        Returns:
            The best feasible solution found across the entire run.
        """
        cfg = self.config
        best_solution: Solution | None = None
        population: list[Solution] = []

        try:
            # ── Phase 1: Initialize population ──────────────────────
            population = initialize_population(
                instance=self.instance,
                pop_size=cfg.pop_size,
                tracker=self.tracker,
                rng=self.rng,
                nn_fraction=cfg.nn_fraction,
            )
            best_solution = population[0]  # Sorted by cost

            generation = 0

            # ── Phase 2: Evolutionary loop ──────────────────────────
            while True:
                generation += 1

                for _ in range(cfg.offspring_size):
                    child = self._create_offspring(population)
                    child = local_search(child, self.instance, self.tracker)

                    # Track global best
                    if child.cost < best_solution.cost:
                        best_solution = Solution(
                            routes=[list(r) for r in child.routes],
                            cost=child.cost,
                            giant_tour=list(child.giant_tour),
                        )

                    population.append(child)

                # ── Elitist (μ + λ) replacement ─────────────────────
                population = self._survivor_selection(population, cfg.pop_size)

        except BudgetExhausted:
            # Normal termination: FE budget exhausted
            # Check if any solution in the current population is better
            if population:
                pop_best = min(population, key=lambda s: s.cost)
                if best_solution is None or pop_best.cost < best_solution.cost:
                    best_solution = pop_best

        if best_solution is None:
            raise RuntimeError("HGA terminated without producing any solution")

        return best_solution

    def _create_offspring(self, population: list[Solution]) -> Solution:
        """Generate a single offspring via selection, crossover, mutation, and split.

        Args:
            population: Current population for parent selection.

        Returns:
            New solution decoded from the offspring chromosome.
        """
        cfg = self.config

        # Selection
        parent1 = tournament_selection(
            population, self.rng, cfg.tournament_size
        )
        parent2 = tournament_selection(
            population, self.rng, cfg.tournament_size
        )

        # Crossover
        if self.rng.random() < cfg.p_crossover:
            child_tour = ox1_crossover(parent1, parent2, self.rng)
        else:
            # No crossover: clone better parent
            child_tour = list(parent1.giant_tour)

        # Mutation
        child_tour = mutate(
            child_tour,
            self.rng,
            p_swap=cfg.p_swap,
            p_inversion=cfg.p_inversion,
            p_insertion=cfg.p_insertion,
        )

        # Decode via Split
        child = split(child_tour, self.instance)
        self.tracker.record(child.cost)  # +1 FE

        return child

    @staticmethod
    def _survivor_selection(
        population: list[Solution],
        target_size: int,
    ) -> list[Solution]:
        """Elitist (μ + λ) replacement with duplicate elimination.

        Sorts merged parents + offspring by cost, removes individuals
        with duplicate giant tours (keeping the first occurrence), and
        returns the best ``target_size`` unique individuals.

        Args:
            population: Merged pool of parents and offspring.
            target_size: Desired population size (μ).

        Returns:
            Reduced population of at most ``target_size`` individuals.
        """
        population.sort(key=lambda s: s.cost)

        seen: set[tuple[int, ...]] = set()
        unique: list[Solution] = []

        for sol in population:
            tour_key = tuple(sol.giant_tour)
            if tour_key not in seen:
                seen.add(tour_key)
                unique.append(sol)

        return unique[:target_size]
