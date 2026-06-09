"""
Notification App Backend — FastAPI Application

Campus notification platform with priority inbox, real-time notification
streaming, and comprehensive lifecycle logging.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse

# Ensure project root is on sys.path for logging_middleware import
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from logging_middleware.logger import Log
from priority_inbox import get_top_n_notifications, PriorityInbox, compute_priority_score

# ── App Configuration ────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: runs startup and shutdown logic."""
    await Log("backend", "info", "config", "Notification App Backend started on port 8002")
    yield
    await Log("backend", "info", "config", "Notification App Backend shutting down")


app = FastAPI(
    title="Notification App Backend",
    description="Campus notification platform with priority inbox.",
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

async def fetch_notifications() -> list[dict]:
    """Fetch notification data from the evaluation service."""
    token = _read_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/notifications"

    await Log("backend", "info", "service", f"Fetching notifications from {url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        await Log("backend", "error", "service",
                  f"Failed to fetch notifications: status {response.status_code}")
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch notifications from evaluation service"
        )

    data = response.json()
    notifications = data.get("notifications", [])
    await Log("backend", "info", "service",
              f"Fetched {len(notifications)} notifications successfully")
    return notifications


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
    return {"status": "running", "service": "notification-app-backend"}


@app.get("/notifications")
async def get_notifications():
    """Fetch and return all notifications from the evaluation service."""
    await Log("backend", "info", "route", "GET /notifications endpoint called")

    notifications = await fetch_notifications()

    await Log("backend", "debug", "controller",
              f"Returning {len(notifications)} raw notifications")

    return {
        "notifications": notifications,
        "total": len(notifications),
    }


@app.get("/notifications/priority")
async def get_priority_notifications(
    n: int = Query(default=10, ge=1, le=100, description="Number of top notifications to return")
):
    """
    Priority Inbox — return the top N most important notifications.

    Priority is determined by:
    1. Type weight: Placement (3) > Result (2) > Event (1)
    2. Recency: more recent notifications rank higher

    Uses a min-heap of size N for O(M log N) efficiency.
    """
    await Log("backend", "info", "route",
              f"GET /notifications/priority?n={n} endpoint called")

    # Fetch notifications from evaluation service
    notifications = await fetch_notifications()

    await Log("backend", "debug", "service",
              f"Computing priority inbox: top {n} from {len(notifications)} notifications")

    # Compute top N using heap-based algorithm
    top_notifications = get_top_n_notifications(notifications, n=n)

    await Log("backend", "info", "service",
              f"Priority inbox computed: returning top {len(top_notifications)} notifications")

    # Log the top result for observability
    if top_notifications:
        top = top_notifications[0]
        await Log("backend", "debug", "service",
                  f"Top priority: [{top.get('Type')}] {top.get('Message')} "
                  f"(score={top.get('priority_score')})")

    return {
        "top_n": n,
        "total_available": len(notifications),
        "priority_notifications": top_notifications,
    }


@app.get("/notifications/{notification_id}")
async def get_notification_by_id(notification_id: str):
    """Fetch a specific notification by ID."""
    await Log("backend", "info", "route",
              f"GET /notifications/{notification_id} endpoint called")

    notifications = await fetch_notifications()

    for notif in notifications:
        if notif.get("ID") == notification_id:
            # Enrich with priority score
            score = compute_priority_score(notif)
            await Log("backend", "info", "controller",
                      f"Found notification {notification_id}: type={notif.get('Type')}")
            return {
                "notification": {
                    **notif,
                    "priority_score": score,
                }
            }

    await Log("backend", "warn", "controller",
              f"Notification {notification_id} not found")
    raise HTTPException(status_code=404, detail="Notification not found")


# ── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
