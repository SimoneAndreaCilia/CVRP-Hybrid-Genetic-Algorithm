"""Convergence graph generation using matplotlib.

Produces publication-quality plots of Fitness (cost) vs. Fitness
Evaluations (FE) with one curve per independent run.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


def plot_convergence(
    instance_name: str,
    convergence_logs: list[list[tuple[int, float]]],
    output_dir: str,
) -> Path:
    """Generate and save a convergence plot for one CVRP instance.

    Plots the best-known cost as a function of fitness evaluations
    for each independent run, overlaid on a single figure.

    Args:
        instance_name: Instance identifier (used in title and filename).
        convergence_logs: One list of ``(fe, best_cost)`` tuples per run.
        output_dir: Directory to save the plot image.

    Returns:
        Path to the saved plot image.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    colors = plt.cm.tab10.colors  # type: ignore[attr-defined]

    for i, log in enumerate(convergence_logs):
        if not log:
            continue
        fes, costs = zip(*log)
        ax.plot(
            fes,
            costs,
            label=f"Run {i + 1}",
            color=colors[i % len(colors)],
            linewidth=1.5,
            alpha=0.8,
        )

    ax.set_xlabel("Fitness Evaluations (FE)", fontsize=12)
    ax.set_ylabel("Best Cost", fontsize=12)
    ax.set_title(f"Convergence — {instance_name}", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.tick_params(labelsize=10)

    fig.tight_layout()

    output_path = Path(output_dir) / f"{instance_name}_convergence.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path
