# Campus Backend Services

A collection of backend microservices built with **FastAPI** (Python), featuring centralized logging middleware and production-grade architecture.

## Assignment Deliverables
- **Vehicle Maintenance Scheduler**: Full implementation in `vehicle_maintence_scheduler/`
- **Notification App Backend**: Priority inbox implementation in `notification_app_be/`
- **System Design Document**: Stages 1-5 answered in `notification_system_design.md`
- **Screenshots**: Execution proofs available in the `Screenshots/` directory.

## Project Structure

```
├── logging_middleware/       # Reusable logging package
├── vehicle_maintence_scheduler/  # Vehicle maintenance optimization service
├── notification_app_be/      # Campus notification platform backend
├── notification_system_design.md # System design document
├── requirements.txt          # Python dependencies
└── .gitignore
```

## Setup

```bash
pip install -r requirements.txt
```

## Services

### Logging Middleware
Reusable async logging module that sends structured log events to the centralized evaluation service. Validates `stack`, `level`, and `package` fields via strict enums before making API calls.

### Vehicle Maintenance Scheduler
Microservice that optimizes daily vehicle maintenance scheduling using dynamic programming. Maximizes operational impact scores within available mechanic-hour budgets.

```bash
cd vehicle_maintence_scheduler
python main.py
# Runs on http://localhost:8001
```

### Notification App Backend
Campus notification platform backend with priority inbox, real-time updates, and notification lifecycle management.

```bash
cd notification_app_be
python main.py
# Runs on http://localhost:8002
```

## Tech Stack

- **Framework**: FastAPI
- **Server**: Uvicorn
- **HTTP Client**: httpx (async)
- **Configuration**: pydantic-settings
