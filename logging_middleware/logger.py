"""
Reusable logging middleware module.
Sends structured log events to the evaluation service API.
"""

from enum import Enum
from pathlib import Path

import httpx

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
BASE_URL = "http://4.224.186.213/evaluation-service"


# ── Strict enums for input validation ────────────────────────────────

class Stack(str, Enum):
    BACKEND = "backend"


class Level(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class Package(str, Enum):
    CACHE = "cache"
    CONTROLLER = "controller"
    CRON_JOB = "cron_job"
    DB = "db"
    DOMAIN = "domain"
    HANDLER = "handler"
    REPOSITORY = "repository"
    ROUTE = "route"
    SERVICE = "service"
    AUTH = "auth"
    CONFIG = "config"
    MIDDLEWARE = "middleware"
    UTILS = "utils"


# ── Helpers ──────────────────────────────────────────────────────────

def _read_access_token() -> str:
    """Read ACCESS_TOKEN from the project .env file."""
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env file not found at {ENV_FILE}")

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("ACCESS_TOKEN="):
            token = line.split("=", 1)[1].strip()
            if not token:
                raise ValueError("ACCESS_TOKEN is empty in .env file")
            return token

    raise KeyError("ACCESS_TOKEN not found in .env file")


def _validate_input(value: str, enum_cls: type[Enum], field_name: str) -> str:
    """
    Validate that a value is lowercase and matches an allowed enum member.
    Raises ValueError with a descriptive message on failure.
    """
    if value != value.lower():
        raise ValueError(
            f"'{field_name}' must be lowercase. Got '{value}'."
        )

    allowed = [member.value for member in enum_cls]
    if value not in allowed:
        raise ValueError(
            f"Invalid {field_name}: '{value}'. "
            f"Allowed values: {allowed}"
        )

    return value


# ── Core logging function ────────────────────────────────────────────

async def log_event(
    stack: str,
    level: str,
    package: str,
    message: str,
) -> dict:
    """
    Send a structured log event to the evaluation service.

    Args:
        stack:   Must be 'backend'.
        level:   One of 'debug', 'info', 'warn', 'error', 'fatal'.
        package: One of 'cache', 'controller', 'cron_job', 'db', 'domain',
                 'handler', 'repository', 'route', 'service', 'auth',
                 'config', 'middleware', 'utils'.
        message: Free-text log message.

    Returns:
        The JSON response body from the API.

    Raises:
        ValueError: If any input fails validation.
        httpx.HTTPStatusError: If the API returns a non-success status.
    """
    # Validate inputs strictly before making any network call
    _validate_input(stack, Stack, "stack")
    _validate_input(level, Level, "level")
    _validate_input(package, Package, "package")

    if not message or not message.strip():
        raise ValueError("'message' must be a non-empty string.")

    # Truncate message to 48 characters to comply with remote server limits
    if len(message) > 48:
        message = message[:45] + "..."

    # Read token
    access_token = _read_access_token()

    # Build request
    url = f"{BASE_URL}/logs"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "stack": stack,
        "level": level,
        "package": package,
        "message": message,
    }

    # Fire async POST
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code in (200, 201):
            print(f"[LOG OK] [{level.upper()}] [{package}] {message}")
            return response.json()
        else:
            print(
                f"[LOG FAIL] Status {response.status_code} — {response.text}"
            )
            return {"error": response.status_code, "detail": response.text}

    except httpx.RequestError as exc:
        print(f"[LOG FAIL] Network error: {exc}")
        return {"error": "network_error", "detail": str(exc)}


# Alias for doc-compliant usage: Log(stack, level, package, message)
Log = log_event
