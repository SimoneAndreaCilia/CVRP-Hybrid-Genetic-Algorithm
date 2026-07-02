"""FastAPI Backend for the CVRP HGA Web Visualizer."""

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.hga import HybridGeneticAlgorithm
from src.models import FitnessTracker, HGAConfig
from src.parser import parse_vrp

app = FastAPI(title="CVRP HGA Visualizer API")

# Mount static files for the frontend
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    """Redirect root to the static index.html."""
    return RedirectResponse(url="/static/index.html")

def get_bks(vrp_path: Path) -> float | None:
    """Read the BKS from the corresponding .sol file if it exists."""
    sol_files = list(vrp_path.parent.rglob(f"{vrp_path.stem}.sol"))
    if not sol_files:
        return None
    try:
        with open(sol_files[0], 'r') as f:
            for line in f:
                if line.startswith("Cost"):
                    return float(line.strip().split()[-1])
    except Exception:
        pass
    return None

class InstanceInfo(BaseModel):
    customers: int
    vehicles: int
    capacity: int

class SolveResponse(BaseModel):
    cost: float
    gap: float | None
    execution_time_ms: float
    fes: int
    routes: list[list[dict[str, float | int]]]
    depot: dict[str, float]
    instance_info: InstanceInfo

@app.get("/api/instances")
def list_instances():
    """Scan test_sets directory and return available instances."""
    test_sets_dir = Path(__file__).parent / "test_sets"
    instances = []
    
    for vrp_file in test_sets_dir.rglob("*.vrp"):
        name = vrp_file.stem
        bks = get_bks(vrp_file)
        instances.append({
            "name": name,
            "path": str(vrp_file.relative_to(Path(__file__).parent).as_posix()),
            "bks": bks
        })
    
    # Sort alphabetically
    instances.sort(key=lambda x: x["name"])
    return instances

@app.post("/api/solve/{instance_name}", response_model=SolveResponse)
def solve_instance(instance_name: str, path: str):
    """Run HGA on the selected instance and return physical routes."""
    instance_path = Path(__file__).parent / path
    if not instance_path.exists():
        return {"error": "Instance not found"}

    # 1. Parse instance
    instance = parse_vrp(str(instance_path))
    
    # 2. Setup tracker and HGA
    # We use a slightly smaller budget for snappy UI feedback, or the standard one.
    # 350k FEs runs in ~0.5s anyway, so we keep the standard budget.
    tracker = FitnessTracker(max_fe=350_000)
    config = HGAConfig()
    hga = HybridGeneticAlgorithm(instance=instance, tracker=tracker, seed=42, config=config)
    
    # 3. Solve
    t0 = time.perf_counter()
    best_solution = hga.run()
    t1 = time.perf_counter()
    
    # 4. Map routes to coordinates
    geometric_routes = []
    for route in best_solution.routes:
        geom_route = []
        # Add depot at start
        depot_coords = instance.coords[instance.depot]
        geom_route.append({"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])})
        
        # Add customers
        for customer_id in route:
            coords = instance.coords[customer_id]
            demand = instance.demands[customer_id]
            geom_route.append({"id": int(customer_id), "demand": int(demand), "x": float(coords[0]), "y": float(coords[1])})
            
        # Add depot at end
        geom_route.append({"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])})
        geometric_routes.append(geom_route)
        
    bks = get_bks(instance_path)
    gap = ((best_solution.cost - bks) / bks * 100) if bks else None
    
    return SolveResponse(
        cost=best_solution.cost,
        gap=gap,
        execution_time_ms=(t1 - t0) * 1000,
        fes=tracker.best_fe,
        routes=geometric_routes,
        depot={"x": float(depot_coords[0]), "y": float(depot_coords[1])},
        instance_info=InstanceInfo(
            customers=instance.dimension - 1,
            vehicles=int(instance.name.split("-k")[-1]),
            capacity=instance.capacity
        )
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)
