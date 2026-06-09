"""
Vehicle Maintenance Scheduler Microservice

Optimizes daily vehicle maintenance scheduling using the 0/1 Knapsack
dynamic programming algorithm. Maximizes total operational impact scores
within available mechanic-hour budgets per depot.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# Ensure project root is on sys.path for logging_middleware import
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from logging_middleware.logger import Log

# ── App Configuration ────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: runs startup and shutdown logic."""
    await Log("backend", "info", "config", "Vehicle Maintenance Scheduler started on port 8001")
    yield
    await Log("backend", "info", "config", "Vehicle Maintenance Scheduler shutting down")


app = FastAPI(
    title="Vehicle Maintenance Scheduler",
    description="Optimizes vehicle maintenance scheduling using dynamic programming.",
    version="1.0.0",
    lifespan=lifespan,
)

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
BASE_URL = "http://4.224.186.213/evaluation-service"


def _read_access_token() -> str:
    """Read ACCESS_TOKEN from the project .env file."""
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env file not found at {ENV_FILE}")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("ACCESS_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise KeyError("ACCESS_TOKEN not found in .env")


# ── Data Fetching ────────────────────────────────────────────────────

async def fetch_depots() -> list[dict]:
    """Fetch depot data from the evaluation service."""
    token = _read_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/depots"

    await Log("backend", "info", "service", f"Fetching depots from {url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        await Log("backend", "error", "service",
                  f"Failed to fetch depots: status {response.status_code}")
        raise HTTPException(status_code=502, detail="Failed to fetch depots from evaluation service")

    data = response.json()
    depots = data.get("depots", [])
    await Log("backend", "info", "service", f"Fetched {len(depots)} depots successfully")
    return depots


async def fetch_vehicles() -> list[dict]:
    """Fetch vehicle/task data from the evaluation service."""
    token = _read_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/vehicles"

    await Log("backend", "info", "service", f"Fetching vehicles from {url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        await Log("backend", "error", "service",
                  f"Failed to fetch vehicles: status {response.status_code}")
        raise HTTPException(status_code=502, detail="Failed to fetch vehicles from evaluation service")

    data = response.json()
    vehicles = data.get("vehicles", [])
    await Log("backend", "info", "service", f"Fetched {len(vehicles)} vehicle tasks successfully")
    return vehicles


# ── Knapsack Algorithm (0/1 Dynamic Programming) ────────────────────

def knapsack_01(items: list[dict], capacity: int) -> list[dict]:
    """
    Solve the 0/1 Knapsack problem using bottom-up dynamic programming.

    Args:
        items: List of dicts with 'Duration' (weight) and 'Impact' (value).
        capacity: Maximum mechanic-hours available (knapsack capacity).

    Returns:
        List of selected items that maximize total Impact within capacity.

    Time Complexity:  O(n * capacity)
    Space Complexity: O(n * capacity)
    """
    n = len(items)
    if n == 0 or capacity <= 0:
        return []

    # Build DP table
    # dp[i][w] = max impact using first i items with capacity w
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        weight = items[i - 1]["Duration"]
        value = items[i - 1]["Impact"]

        for w in range(capacity + 1):
            # Don't take item i
            dp[i][w] = dp[i - 1][w]

            # Take item i (if it fits)
            if weight <= w:
                take = dp[i - 1][w - weight] + value
                if take > dp[i][w]:
                    dp[i][w] = take

    # Backtrack to find selected items
    selected = []
    w = capacity
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            selected.append(items[i - 1])
            w -= items[i - 1]["Duration"]

    selected.reverse()
    return selected


# ── Exception Handler ────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions and return a generic 500 response."""
    await Log("backend", "error", "handler", f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )





# ── Routes ───────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Basic sanity check endpoint."""
    await Log("backend", "info", "route", "Health check endpoint called")
    return {"status": "running", "service": "vehicle-maintenance-scheduler"}


@app.get("/depots")
async def get_depots():
    """Fetch and return all available depots from the evaluation service."""
    await Log("backend", "info", "route", "GET /depots endpoint called")
    depots = await fetch_depots()
    return {"depots": depots, "total": len(depots)}


@app.get("/vehicles")
async def get_vehicles():
    """Fetch and return all vehicle maintenance tasks from the evaluation service."""
    await Log("backend", "info", "route", "GET /vehicles endpoint called")
    vehicles = await fetch_vehicles()
    return {"vehicles": vehicles, "total": len(vehicles)}


@app.get("/schedule/{depot_id}")
async def get_schedule(depot_id: int):
    """
    Compute the optimal maintenance schedule for a specific depot.

    Uses 0/1 Knapsack DP to maximize total impact score within the
    depot's available mechanic-hours budget.
    """
    await Log("backend", "info", "route", f"GET /schedule/{depot_id} endpoint called")

    # Fetch data from evaluation service
    depots = await fetch_depots()
    vehicles = await fetch_vehicles()

    # Find the requested depot
    depot = None
    for d in depots:
        if d["ID"] == depot_id:
            depot = d
            break

    if depot is None:
        await Log("backend", "warn", "route",
                  f"Depot {depot_id} not found. Available IDs: {[d['ID'] for d in depots]}")
        raise HTTPException(status_code=404, detail=f"Depot with ID {depot_id} not found")

    capacity = depot["MechanicHours"]
    await Log("backend", "info", "service",
              f"Depot {depot_id}: capacity={capacity}h, tasks={len(vehicles)}")

    # Run knapsack algorithm
    await Log("backend", "debug", "service",
              f"Running 0/1 Knapsack DP: n={len(vehicles)}, W={capacity}")

    selected = knapsack_01(vehicles, capacity)

    # Calculate totals
    total_duration = sum(v["Duration"] for v in selected)
    total_impact = sum(v["Impact"] for v in selected)

    # Determine unselected vehicles
    selected_ids = {v["TaskID"] for v in selected}
    unselected = [v for v in vehicles if v["TaskID"] not in selected_ids]

    await Log("backend", "info", "service",
              f"Knapsack result: selected {len(selected)}/{len(vehicles)} tasks, "
              f"impact={total_impact}, hours_used={total_duration}/{capacity}")

    return {
        "depot_id": depot_id,
        "mechanic_hours_available": capacity,
        "mechanic_hours_used": total_duration,
        "total_impact_score": total_impact,
        "tasks_selected": len(selected),
        "tasks_total": len(vehicles),
        "selected_vehicles": selected,
        "unselected_vehicles": unselected,
    }


@app.get("/schedule")
async def get_all_schedules():
    """
    Compute the optimal maintenance schedule for ALL depots.
    Returns a summary and per-depot breakdown.
    """
    await Log("backend", "info", "route", "GET /schedule (all depots) endpoint called")

    depots = await fetch_depots()
    vehicles = await fetch_vehicles()

    results = []
    for depot in depots:
        depot_id = depot["ID"]
        capacity = depot["MechanicHours"]

        await Log("backend", "debug", "service",
                  f"Processing depot {depot_id}: capacity={capacity}h")

        selected = knapsack_01(vehicles, capacity)
        total_duration = sum(v["Duration"] for v in selected)
        total_impact = sum(v["Impact"] for v in selected)

        selected_ids = {v["TaskID"] for v in selected}
        unselected = [v for v in vehicles if v["TaskID"] not in selected_ids]

        results.append({
            "depot_id": depot_id,
            "mechanic_hours_available": capacity,
            "mechanic_hours_used": total_duration,
            "total_impact_score": total_impact,
            "tasks_selected": len(selected),
            "tasks_total": len(vehicles),
            "selected_vehicles": selected,
            "unselected_vehicles": unselected,
        })

        await Log("backend", "info", "service",
                  f"Depot {depot_id}: impact={total_impact}, "
                  f"hours={total_duration}/{capacity}")

    await Log("backend", "info", "service",
              f"Computed schedules for {len(results)} depots")

    return {
        "total_depots": len(results),
        "schedules": results,
    }


# ── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
