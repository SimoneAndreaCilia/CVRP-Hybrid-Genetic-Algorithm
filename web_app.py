"""FastAPI Backend for the CVRP HGA Web Visualizer."""

import time
from pathlib import Path
import statistics

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

def parse_sol_file(vrp_path: Path) -> dict | None:
    """Parse the corresponding .sol file to extract optimal cost and routes."""
    sol_files = list(vrp_path.parent.rglob(f"{vrp_path.stem}.sol"))
    if not sol_files:
        return None
    
    sol_data = {"cost": None, "routes": []}
    try:
        with open(sol_files[0], 'r') as f:
            for line in f:
                if line.startswith("Cost"):
                    sol_data["cost"] = float(line.strip().split()[-1])
                elif line.startswith("Route"):
                    parts = line.split(":")
                    if len(parts) == 2:
                        route_str = parts[1].strip()
                        route_nodes = [int(n) for n in route_str.split() if n.strip().isdigit()]
                        if route_nodes:
                            sol_data["routes"].append(route_nodes)
        if sol_data["cost"] is not None:
            return sol_data
    except Exception:
        pass
    return None

def get_bks(vrp_path: Path) -> float | None:
    data = parse_sol_file(vrp_path)
    return data["cost"] if data else None

def extract_edges(routes: list[list[int]], depot: int) -> set[frozenset[int]]:
    """Extract undirected edges from a list of CVRP routes."""
    edges = set()
    for route in routes:
        if not route: continue
        edges.add(frozenset([depot, route[0]]))
        for i in range(len(route) - 1):
            edges.add(frozenset([route[i], route[i+1]]))
        edges.add(frozenset([route[-1], depot]))
    return edges


class SolveRequest(BaseModel):
    path: str
    seed: int | None = None
    max_fe: int = 350000
    pop_size: int = 50
    mutation_rate: float = 0.4
    use_local_search: bool = True

class ProtocolRunStat(BaseModel):
    seed: int
    cost: float
    gap: float | None
    fes: int
    execution_time_ms: float
    is_feasible: bool

class InstanceInfo(BaseModel):
    customers: int
    vehicles: int
    capacity: int

class ProtocolResponse(BaseModel):
    best_cost: float
    mean_cost: float
    std_cost: float
    gap: float | None
    avg_fes: float
    runs: list[ProtocolRunStat]
    routes: list[list[dict[str, float | int]]]
    bks_routes: list[list[dict[str, float | int]]] | None
    depot: dict[str, float]
    instance_info: InstanceInfo

class SolveResponse(BaseModel):
    cost: float
    gap: float | None
    edge_similarity: float | None
    execution_time_ms: float
    fes: int
    routes: list[list[dict[str, float | int]]]
    bks_routes: list[list[dict[str, float | int]]] | None
    depot: dict[str, float]
    instance_info: InstanceInfo
    convergence_log: list[tuple[int, float]]
    customers_served: int
    is_feasible: bool

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
def solve_instance(instance_name: str, req: SolveRequest):
    """Run HGA on the selected instance and return physical routes."""
    instance_path = Path(__file__).parent / req.path
    if not instance_path.exists():
        return {"error": "Instance not found"}

    # 1. Parse instance
    instance = parse_vrp(str(instance_path))
    
    # 2. Setup tracker and HGA
    tracker = FitnessTracker(max_fe=req.max_fe)
    m_ratio = req.mutation_rate / 0.4 if req.mutation_rate > 0 else 0
    config = HGAConfig(
        pop_size=req.pop_size,
        p_swap=0.15 * m_ratio,
        p_inversion=0.15 * m_ratio,
        p_insertion=0.10 * m_ratio,
        use_local_search=req.use_local_search
    )
    hga = HybridGeneticAlgorithm(instance=instance, tracker=tracker, seed=req.seed, config=config)
    
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
        
    # 5. Compare with BKS
    sol_data = parse_sol_file(instance_path)
    gap = None
    edge_similarity = None
    bks_geometric_routes = None
    
    if sol_data and sol_data["cost"]:
        bks = sol_data["cost"]
        gap = ((best_solution.cost - bks) / bks * 100)
        
        # Calculate edge similarity and map geometric routes
        if sol_data["routes"]:
            hga_edges = extract_edges(best_solution.routes, instance.depot)
            bks_edges = extract_edges(sol_data["routes"], instance.depot)
            if bks_edges:
                common = len(hga_edges.intersection(bks_edges))
                edge_similarity = (common / len(bks_edges)) * 100
                
            # Build geometric BKS routes for UI comparison
            bks_geometric_routes = []
            for route in sol_data["routes"]:
                geom_route = []
                geom_route.append({"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])})
                for customer_id in route:
                    coords = instance.coords[customer_id]
                    demand = instance.demands[customer_id]
                    geom_route.append({"id": int(customer_id), "demand": int(demand), "x": float(coords[0]), "y": float(coords[1])})
                geom_route.append({"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])})
                bks_geometric_routes.append(geom_route)
    
    return SolveResponse(
        cost=best_solution.cost,
        gap=gap,
        edge_similarity=edge_similarity,
        execution_time_ms=(t1 - t0) * 1000,
        fes=tracker.best_fe,
        routes=geometric_routes,
        bks_routes=bks_geometric_routes,
        depot={"x": float(depot_coords[0]), "y": float(depot_coords[1])},
        instance_info=InstanceInfo(
            customers=instance.dimension - 1,
            vehicles=int(instance.name.split("-k")[-1]),
            capacity=instance.capacity
        ),
        convergence_log=tracker.convergence_log,
        customers_served=best_solution.num_visited,
        is_feasible=best_solution.is_feasible(instance)
    )


@app.post("/api/solve-protocol/{instance_name}", response_model=ProtocolResponse)
def solve_protocol(instance_name: str, req: SolveRequest):
    """Run 5 independent seeded runs (Protocol Mode)."""
    instance_path = Path(__file__).parent / req.path
    if not instance_path.exists():
        return {"error": "Instance not found"}
        
    instance = parse_vrp(str(instance_path))
    sol_data = parse_sol_file(instance_path)
    bks = sol_data["cost"] if (sol_data and sol_data["cost"]) else None
    
    m_ratio = req.mutation_rate / 0.4 if req.mutation_rate > 0 else 0
    config = HGAConfig(
        pop_size=req.pop_size,
        p_swap=0.15 * m_ratio,
        p_inversion=0.15 * m_ratio,
        p_insertion=0.10 * m_ratio,
        use_local_search=req.use_local_search
    )
    
    run_stats = []
    costs = []
    fes_list = []
    
    seeds = [1, 2, 3, 4, 5]
    global_best_solution = None
    global_best_cost = float('inf')
    
    for seed in seeds:
        tracker = FitnessTracker(max_fe=req.max_fe)
        hga = HybridGeneticAlgorithm(instance=instance, tracker=tracker, seed=seed, config=config)
        
        t0 = time.perf_counter()
        best_solution = hga.run()
        t1 = time.perf_counter()
        
        cost = best_solution.cost
        fes = tracker.best_fe
        feasible = best_solution.is_feasible(instance)
        
        if cost < global_best_cost:
            global_best_cost = cost
            global_best_solution = best_solution
            
        costs.append(cost)
        fes_list.append(fes)
        
        gap = ((cost - bks) / bks * 100) if bks else None
        
        run_stats.append(ProtocolRunStat(
            seed=seed,
            cost=cost,
            gap=gap,
            fes=fes,
            execution_time_ms=(t1 - t0) * 1000,
            is_feasible=feasible
        ))
        
    best_cost = min(costs)
    mean_cost = statistics.mean(costs)
    std_cost = statistics.stdev(costs) if len(costs) > 1 else 0.0
    avg_fes = statistics.mean(fes_list)
    best_gap = ((best_cost - bks) / bks * 100) if bks else None
    
    # Map routes to coordinates for the best run
    depot_coords = instance.coords[instance.depot]
    geometric_routes = []
    for route in global_best_solution.routes:
        geom_route = [{"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])}]
        for customer_id in route:
            coords = instance.coords[customer_id]
            demand = instance.demands[customer_id]
            geom_route.append({"id": int(customer_id), "demand": int(demand), "x": float(coords[0]), "y": float(coords[1])})
        geom_route.append({"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])})
        geometric_routes.append(geom_route)

    # BKS routes for comparison
    bks_geometric_routes = None
    if sol_data and sol_data["routes"]:
        bks_geometric_routes = []
        for route in sol_data["routes"]:
            geom_route = [{"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])}]
            for customer_id in route:
                coords = instance.coords[customer_id]
                demand = instance.demands[customer_id]
                geom_route.append({"id": int(customer_id), "demand": int(demand), "x": float(coords[0]), "y": float(coords[1])})
            geom_route.append({"id": 0, "demand": 0, "x": float(depot_coords[0]), "y": float(depot_coords[1])})
            bks_geometric_routes.append(geom_route)

    return ProtocolResponse(
        best_cost=best_cost,
        mean_cost=mean_cost,
        std_cost=std_cost,
        gap=best_gap,
        avg_fes=avg_fes,
        runs=run_stats,
        routes=geometric_routes,
        bks_routes=bks_geometric_routes,
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
