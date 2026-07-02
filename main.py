"""Experimental runner for the CVRP Hybrid Genetic Algorithm solver.

Implements the strict experimental protocol:
    - 10 benchmark instances (sets A, B, E, P)
    - 5 independent runs per instance (deterministic seeds 1–5)
    - 350,000 FE budget per run
    - Statistical reporting: Best, Mean, Std Dev, Satisfiability, Avg FE@best
    - Convergence plots for 3 representative instances
    - CSV export of all results
"""

from __future__ import annotations

import csv
import statistics
import sys
import time
from pathlib import Path

from src.hga import HybridGeneticAlgorithm
from src.models import FitnessTracker, HGAConfig
from src.parser import parse_vrp
from src.visualization import plot_convergence

# ── Configuration ───────────────────────────────────────────────────────────

INSTANCES: list[str] = [
    "test_sets/set_A/A-n45-k7.vrp",
    "test_sets/set_A/A-n60-k9.vrp",
    "test_sets/set_A/A-n80-k10.vrp",
    "test_sets/set_B/B-n56-k7.vrp",
    "test_sets/set_B/B-n66-k9.vrp",
    "test_sets/set_B/B-n78-k10.vrp",
    "test_sets/set_E/E-n76-k8.vrp",
    "test_sets/set_E/E-n101-k14.vrp",
    "test_sets/set_P/P-n50-k10.vrp",
    "test_sets/set_P/P-n101-k4.vrp",
]

# Best Known Solutions from CVRPLIB (for gap% computation)
BKS: dict[str, float] = {
    "A-n45-k7": 1146,
    "A-n60-k9": 1354,
    "A-n80-k10": 1763,
    "B-n56-k7": 707,
    "B-n66-k9": 1316,
    "B-n78-k10": 1266,
    "E-n76-k8": 735,
    "E-n101-k14": 1071,
    "P-n50-k10": 696,
    "P-n101-k4": 681,
}

# Instances for convergence plots (small, medium, large from different sets)
PLOT_INSTANCES: set[str] = {"A-n45-k7", "E-n76-k8", "P-n101-k4"}

MAX_FE: int = 350_000
NUM_RUNS: int = 5
SEEDS: list[int] = [1, 2, 3, 4, 5]


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the full experimental protocol and generate reports."""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    all_results: list[dict[str, object]] = []

    print("=" * 90)
    print("  CVRP Hybrid Genetic Algorithm -- Experimental Runner")
    print(f"  FE Budget: {MAX_FE:,} | Runs per instance: {NUM_RUNS}")
    print("=" * 90)

    for instance_path in INSTANCES:
        instance = parse_vrp(instance_path)
        bks = BKS.get(instance.name, float("inf"))

        print(f"\n{'-' * 90}")
        print(
            f"  Instance: {instance.name}  |  "
            f"Customers: {instance.num_customers}  |  "
            f"Capacity: {instance.capacity}  |  "
            f"BKS: {bks:.0f}"
        )
        print(f"{'-' * 90}")

        run_best_costs: list[float] = []
        run_fes_at_best: list[int] = []
        convergence_logs: list[list[tuple[int, float]]] = []
        best_overall_solution = None

        for run_idx in range(NUM_RUNS):
            seed = SEEDS[run_idx]
            sys.stdout.write(
                f"  Run {run_idx + 1}/{NUM_RUNS} (seed={seed}) ... "
            )
            sys.stdout.flush()

            tracker = FitnessTracker(max_fe=MAX_FE)
            config = HGAConfig()
            hga = HybridGeneticAlgorithm(
                instance=instance, tracker=tracker, seed=seed, config=config
            )

            start_time = time.perf_counter()
            best_solution = hga.run()
            elapsed = time.perf_counter() - start_time

            run_best_costs.append(best_solution.cost)
            run_fes_at_best.append(tracker.best_fe)
            convergence_logs.append(list(tracker.convergence_log))

            if (
                best_overall_solution is None
                or best_solution.cost < best_overall_solution.cost
            ):
                best_overall_solution = best_solution

            feasible = best_solution.is_feasible(instance)
            gap = (
                (best_solution.cost - bks) / bks * 100
                if bks < float("inf")
                else float("nan")
            )
            print(
                f"Cost={best_solution.cost:>8.0f}  "
                f"Gap={gap:>6.2f}%  "
                f"FE@best={tracker.best_fe:>7,}  "
                f"Feasible={feasible}  "
                f"Time={elapsed:>5.1f}s"
            )

        # -- Aggregate statistics ------------------------------------
        assert best_overall_solution is not None
        best_cost = min(run_best_costs)
        mean_cost = statistics.mean(run_best_costs)
        std_cost = (
            statistics.stdev(run_best_costs) if len(run_best_costs) > 1 else 0.0
        )
        avg_fe_at_best = statistics.mean(run_fes_at_best)
        satisfiability = (
            f"{best_overall_solution.num_visited}/{instance.num_customers}"
        )
        gap_best = (
            (best_cost - bks) / bks * 100 if bks < float("inf") else float("nan")
        )

        print(f"\n  {'Summary':-<40}")
        print(f"    Best:          {best_cost:>10.2f}  (gap: {gap_best:.2f}%)")
        print(f"    Mean:          {mean_cost:>10.2f}")
        print(f"    Std Dev:       {std_cost:>10.2f}")
        print(f"    Satisfiability:{satisfiability:>10}")
        print(f"    Avg FE@best:   {avg_fe_at_best:>10,.0f}")

        all_results.append(
            {
                "instance": instance.name,
                "bks": bks,
                "best": best_cost,
                "mean": mean_cost,
                "std": std_cost,
                "gap_pct": round(gap_best, 2),
                "satisfiability": satisfiability,
                "avg_fe_at_best": round(avg_fe_at_best),
            }
        )

        # ── Convergence plot for selected instances ─────────────────
        if instance.name in PLOT_INSTANCES:
            plot_path = plot_convergence(
                instance.name, convergence_logs, str(output_dir)
            )
            print(f"    Plot saved:    {plot_path}")

    # ── Save CSV ────────────────────────────────────────────────────────
    csv_path = output_dir / "results.csv"
    fieldnames = [
        "instance",
        "bks",
        "best",
        "mean",
        "std",
        "gap_pct",
        "satisfiability",
        "avg_fe_at_best",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"\n\nCSV results saved to: {csv_path}")

    # ── Final summary table ─────────────────────────────────────────
    print(f"\n{'=' * 95}")
    print(
        f"  {'Instance':<15} {'BKS':>6} {'Best':>8} {'Mean':>8} "
        f"{'Std':>8} {'Gap%':>7} {'Satisf':>10} {'Avg FE':>10}"
    )
    print(f"{'=' * 95}")
    for r in all_results:
        print(
            f"  {r['instance']:<15} {r['bks']:>6.0f} {r['best']:>8.0f} "
            f"{r['mean']:>8.0f} {r['std']:>8.2f} {r['gap_pct']:>6.2f}% "
            f"{r['satisfiability']:>10} {r['avg_fe_at_best']:>10,}"
        )
    print(f"{'=' * 95}")
    print("\nDone.")


if __name__ == "__main__":
    main()
