# Notification System Design

> Campus notification platform where students receive real-time updates regarding Placements, Events, and Results.

---

## Stage 1

### REST API Design & Contract

#### Base Configuration

| Property | Value |
|----------|-------|
| Base URL | `/api/v1` |
| Content-Type | `application/json` |
| Auth | Pre-authorized (no login required per evaluation spec) |

---

#### 1.1 Core Endpoints

##### `GET /api/v1/notifications`

Fetch all notifications for the logged-in user with filtering and pagination.

**Query Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | No | — | Filter by type: `Placement`, `Result`, `Event` |
| `isRead` | boolean | No | — | Filter by read status |
| `page` | int | No | 1 | Page number |
| `limit` | int | No | 20 | Notifications per page (max 100) |
| `sortBy` | string | No | `createdAt` | Sort field |
| `order` | string | No | `desc` | Sort order: `asc` or `desc` |

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "notifications": [
      {
        "id": "d146095a-0d86-4a34-9e69-3900a14576bc",
        "type": "Result",
        "message": "Mid-semester results published",
        "isRead": false,
        "priority": 2,
        "createdAt": "2026-04-22T17:51:30Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "totalItems": 142,
      "totalPages": 8
    },
    "unreadCount": 35
  }
}
```

---

##### `GET /api/v1/notifications/{id}`

Fetch a single notification by ID.

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": "d146095a-0d86-4a34-9e69-3900a14576bc",
    "type": "Result",
    "message": "Mid-semester results published",
    "isRead": false,
    "priority": 2,
    "createdAt": "2026-04-22T17:51:30Z",
    "readAt": null
  }
}
```

**Error (404):**

```json
{
  "success": false,
  "error": "Notification not found"
}
```

---

##### `POST /api/v1/notifications`

Create a new notification (used by admin/system).

**Request Body:**

```json
{
  "type": "Placement",
  "message": "Google is hiring for SDE roles",
  "targetStudentIds": ["all"]
}
```

**Headers:**

```
Content-Type: application/json
```

**Response (201 Created):**

```json
{
  "success": true,
  "data": {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "type": "Placement",
    "message": "Google is hiring for SDE roles",
    "isRead": false,
    "createdAt": "2026-06-09T06:00:00Z"
  }
}
```

---

##### `PATCH /api/v1/notifications/{id}/read`

Mark a single notification as read.

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": "d146095a-0d86-4a34-9e69-3900a14576bc",
    "isRead": true,
    "readAt": "2026-06-09T06:05:00Z"
  }
}
```

---

##### `PATCH /api/v1/notifications/read-all`

Mark all notifications as read for the current user.

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "markedCount": 35,
    "message": "All notifications marked as read"
  }
}
```

---

##### `DELETE /api/v1/notifications/{id}`

Delete a specific notification.

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "message": "Notification deleted successfully"
  }
}
```

---

##### `GET /api/v1/notifications/count`

Get unread notification count (for badge display on frontend).

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "unreadCount": 35
  }
}
```

---

#### 1.2 Real-Time Notification Mechanism

**Chosen approach: Server-Sent Events (SSE)**

**Why SSE over WebSockets:**

| Criteria | SSE | WebSocket |
|----------|-----|-----------|
| Direction | Server → Client (unidirectional) | Bidirectional |
| Complexity | Simple, built on HTTP | Requires separate protocol |
| Reconnection | Automatic (built-in) | Manual implementation needed |
| Browser support | Native `EventSource` API | Native `WebSocket` API |
| Fit for notifications | ✅ Perfect (server pushes updates) | Overkill (client doesn't push) |

Notifications are inherently **unidirectional** — the server pushes updates to students. SSE is the optimal choice because it's simpler, auto-reconnects, and works over standard HTTP.

##### `GET /api/v1/notifications/stream`

Opens a persistent SSE connection for real-time notifications.

**Headers:**

```
Accept: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**Event Stream Format:**

```
event: notification
data: {"id":"f47ac10b","type":"Placement","message":"Google is hiring","createdAt":"2026-06-09T06:00:00Z"}

event: notification
data: {"id":"a1b2c3d4","type":"Result","message":"Final grades published","createdAt":"2026-06-09T06:01:00Z"}

event: heartbeat
data: {"timestamp":"2026-06-09T06:02:00Z"}
```

**Implementation approach:**

- Backend maintains an in-memory registry of active SSE connections per student.
- When a new notification is created via `POST /api/v1/notifications`, the system publishes it to a Redis Pub/Sub channel.
- Each server instance subscribes to the channel and pushes events to connected students.
- A heartbeat event is sent every 30 seconds to keep the connection alive.

---

## Stage 2

### Database Design

#### 2.1 Database Choice: PostgreSQL

**Why PostgreSQL over alternatives:**

| Criteria | PostgreSQL | MongoDB | MySQL |
|----------|-----------|---------|-------|
| ACID compliance | ✅ Full | Partial | ✅ Full |
| JSON support | ✅ JSONB (indexed) | ✅ Native | Limited |
| Full-text search | ✅ Built-in | ✅ Built-in | Limited |
| Partitioning | ✅ Native | ✅ Sharding | Limited |
| Enum types | ✅ Native | ❌ | ✅ |
| Concurrent writes | ✅ MVCC | ✅ | Lock-based |

PostgreSQL is chosen because:
1. **Relational integrity** — Students, notifications, and preferences have clear relationships.
2. **ENUM types** — Native support for `notification_type` (`Placement`, `Result`, `Event`).
3. **JSONB** — Flexibility for metadata without sacrificing query performance.
4. **Partitioning** — Table partitioning for scaling when data grows.
5. **Mature ecosystem** — Excellent tooling, monitoring, and replication support.

---

#### 2.2 Database Schema

##### `students` table

```sql
CREATE TABLE students (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    roll_no     VARCHAR(50) UNIQUE NOT NULL,
    department  VARCHAR(100),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

##### `notification_type` enum

```sql
CREATE TYPE notification_type AS ENUM ('Placement', 'Result', 'Event');
```

##### `notifications` table

```sql
CREATE TABLE notifications (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id        INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    type              notification_type NOT NULL,
    message           TEXT NOT NULL,
    is_read           BOOLEAN DEFAULT FALSE,
    read_at           TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Composite index for the most frequent query pattern
CREATE INDEX idx_notifications_student_unread
    ON notifications (student_id, is_read, created_at DESC)
    WHERE is_read = FALSE;

-- Index for type-based filtering
CREATE INDEX idx_notifications_type_created
    ON notifications (type, created_at DESC);

-- Index for time-range queries
CREATE INDEX idx_notifications_created_at
    ON notifications (created_at DESC);
```

##### `notification_preferences` table

```sql
CREATE TABLE notification_preferences (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    type            notification_type NOT NULL,
    email_enabled   BOOLEAN DEFAULT TRUE,
    in_app_enabled  BOOLEAN DEFAULT TRUE,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, type)
);
```

---

#### 2.3 Scaling Problems & Solutions

| Problem | When It Happens | Solution |
|---------|-----------------|----------|
| **Table bloat** | Notifications table grows to hundreds of millions of rows | **Table partitioning** by `created_at` (monthly partitions). Archive old partitions to cold storage. |
| **Slow reads** | High-frequency reads (every page load × 50K students) | **Read replicas** for query offloading. Add Redis caching layer (see Stage 4). |
| **Write contention** | Bulk notification sends (50K inserts at once) | **Batch inserts** with `COPY` or multi-row `INSERT`. Use message queues to spread writes over time. |
| **Index overhead** | Too many indexes slow down writes | **Partial indexes** (e.g., only index unread notifications). Drop unused indexes. |
| **Full table scans** | Missing or incorrect indexes | **EXPLAIN ANALYZE** to identify and fix slow queries. Composite indexes on common filter combos. |

**Partitioning strategy:**

```sql
-- Partition by month
CREATE TABLE notifications (
    id          UUID DEFAULT gen_random_uuid(),
    student_id  INTEGER NOT NULL,
    type        notification_type NOT NULL,
    message     TEXT NOT NULL,
    is_read     BOOLEAN DEFAULT FALSE,
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE notifications_2026_06 PARTITION OF notifications
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE notifications_2026_07 PARTITION OF notifications
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
```

---

#### 2.4 SQL Queries for Stage 1 Endpoints

**GET /api/v1/notifications (with filters + pagination):**

```sql
SELECT id, type, message, is_read, created_at
FROM notifications
WHERE student_id = $1
  AND ($2::notification_type IS NULL OR type = $2)
  AND ($3::boolean IS NULL OR is_read = $3)
ORDER BY created_at DESC
LIMIT $4 OFFSET $5;
```

**GET /api/v1/notifications/{id}:**

```sql
SELECT id, type, message, is_read, read_at, created_at
FROM notifications
WHERE id = $1 AND student_id = $2;
```

**POST /api/v1/notifications (bulk insert for all students):**

```sql
INSERT INTO notifications (student_id, type, message)
SELECT id, $1::notification_type, $2
FROM students
WHERE is_active = TRUE;
```

**PATCH /api/v1/notifications/{id}/read:**

```sql
UPDATE notifications
SET is_read = TRUE, read_at = NOW()
WHERE id = $1 AND student_id = $2 AND is_read = FALSE;
```

**PATCH /api/v1/notifications/read-all:**

```sql
UPDATE notifications
SET is_read = TRUE, read_at = NOW()
WHERE student_id = $1 AND is_read = FALSE;
```

**GET /api/v1/notifications/count:**

```sql
SELECT COUNT(*) AS unread_count
FROM notifications
WHERE student_id = $1 AND is_read = FALSE;
```

---

## Stage 3

### Query Optimization

#### 3.1 Analyzing the Slow Query

```sql
SELECT * FROM notifications
WHERE studentID = 1042 AND isRead = false
ORDER BY createdAt DESC;
```

**Is the query accurate?**

Yes, the query is logically correct — it fetches all unread notifications for student 1042, sorted by most recent first. However, it has performance issues.

**Why is it slow?**

With 50,000 students and 5,000,000 notifications, this query suffers from:

1. **Full table scan**: Without a composite index on `(studentID, isRead, createdAt)`, PostgreSQL must scan all 5 million rows, filtering row by row.

2. **`SELECT *` is wasteful**: Fetches all columns including potentially large text fields (message body), even if the frontend only needs `id`, `type`, `message`, and `createdAt`. This increases I/O and memory usage.

3. **No LIMIT clause**: Returns ALL unread notifications at once. A student with 1,000 unread notifications will return all of them — wasting bandwidth and memory.

4. **Filesort for ORDER BY**: Without an index that covers the sort order (`createdAt DESC`), PostgreSQL must perform an in-memory or disk-based sort of the filtered results.

**What would I change:**

```sql
-- Optimized query
SELECT id, type, message, is_read, created_at
FROM notifications
WHERE student_id = 1042 AND is_read = FALSE
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;
```

Changes made:
1. **Explicit column list** instead of `SELECT *` — reduces I/O
2. **Added `LIMIT` and `OFFSET`** — pagination prevents returning thousands of rows
3. **Composite index** (created below) eliminates the full table scan

**Required index:**

```sql
CREATE INDEX idx_notifications_student_unread_time
    ON notifications (student_id, is_read, created_at DESC)
    WHERE is_read = FALSE;
```

This is a **partial composite index** — it only indexes unread notifications, making it smaller and faster. PostgreSQL can:
- Seek directly to `student_id = 1042` (index scan, not table scan)
- Skip read notifications entirely (partial index predicate)
- Return results pre-sorted by `created_at DESC` (no filesort)

**Likely computation cost:**

| Scenario | Cost |
|----------|------|
| Without index (full table scan) | O(N) where N = 5,000,000 — scans every row |
| With composite index (index scan) | O(log N + K) where K = number of unread for that student — typically < 100 |
| With partial index | Even faster — index only contains unread rows, so it's physically smaller |

The query goes from scanning **5 million rows** to seeking through an index of perhaps **200,000 unread rows** and returning only the matching student's subset.

---

#### 3.2 Should We Index Every Column?

> *"Another developer suggests adding indexes on every column to be safe."*

**No, this is NOT effective. It is harmful.**

| Problem | Explanation |
|---------|-------------|
| **Write amplification** | Every `INSERT`, `UPDATE`, or `DELETE` must update ALL indexes. With 5M notifications and bulk sends of 50K at once, each insert would update N indexes instead of 1-2. This dramatically slows writes. |
| **Storage overhead** | Each index consumes disk space. Indexing every column on a 5M-row table could double or triple the storage requirements. |
| **Index maintenance** | PostgreSQL must `VACUUM` and maintain each index. More indexes = longer maintenance windows and higher CPU usage. |
| **Planner confusion** | Too many indexes can confuse the query planner, sometimes choosing suboptimal indexes or spending too much time evaluating plans. |
| **Diminishing returns** | Indexes on low-selectivity columns (e.g., `is_read` which is only `TRUE` or `FALSE`) provide almost no benefit on their own. The planner may skip them entirely. |

**The correct strategy:**
- Index columns that appear in `WHERE`, `JOIN`, and `ORDER BY` clauses of frequent queries.
- Use **composite indexes** that match specific query patterns.
- Use **partial indexes** to reduce index size (e.g., only unread notifications).
- Regularly run `EXPLAIN ANALYZE` to verify indexes are being used.

---

#### 3.3 Placement Notifications in the Last 7 Days

```sql
SELECT s.id, s.name, s.email, s.roll_no, n.message, n.created_at
FROM students s
INNER JOIN notifications n ON s.id = n.student_id
WHERE n.type = 'Placement'
  AND n.created_at >= NOW() - INTERVAL '7 days'
ORDER BY n.created_at DESC;
```

**Supporting index:**

```sql
CREATE INDEX idx_notifications_type_recent
    ON notifications (type, created_at DESC)
    WHERE type = 'Placement';
```

---

## Stage 4

### Caching & Performance Strategy

#### 4.1 The Problem

Notifications are fetched on **every page load** for **every student**. With 50,000 students, even moderate usage (5 page loads/student/day) means:

```
50,000 students × 5 loads/day = 250,000 DB queries/day
Peak hours: ~50 queries/second hitting the DB
```

This overwhelms the database, causing slow response times and degraded user experience.

---

#### 4.2 Solution 1: Redis Caching Layer (Primary)

Cache each student's unread notifications in Redis with a TTL.

```
Key:    notifications:unread:{student_id}
Value:  JSON array of recent unread notifications
TTL:    5 minutes
```

**Read flow:**
1. Check Redis for `notifications:unread:{student_id}`
2. Cache HIT → return cached data (no DB query)
3. Cache MISS → query DB, store result in Redis with 5-min TTL, return data

**Write flow (cache invalidation):**
- When a new notification is created → delete the student's cache key
- When a notification is marked as read → delete the student's cache key
- This ensures the next read fetches fresh data from DB

**Tradeoffs:**

| Advantage | Disadvantage |
|-----------|--------------|
| 90%+ cache hit rate under normal usage | Slight staleness (up to 5 min for TTL-based expiry) |
| Sub-millisecond reads from Redis | Additional infrastructure (Redis cluster) |
| Reduces DB load by 10x | Cache stampede risk if many keys expire simultaneously |
| Simple implementation | Memory cost (~500 bytes × 50K students ≈ 25MB — negligible) |

---

#### 4.3 Solution 2: Pagination (Mandatory)

Never return all notifications at once. Enforce server-side pagination:

```sql
LIMIT 20 OFFSET 0  -- Page 1
LIMIT 20 OFFSET 20 -- Page 2
```

**Tradeoffs:**

| Advantage | Disadvantage |
|-----------|--------------|
| Bounded response size | User must paginate to see older notifications |
| Predictable query cost | OFFSET-based pagination is slow at high offsets |
| Less memory per request | — |

For deep pagination, use **cursor-based pagination** instead of OFFSET:

```sql
WHERE created_at < $last_seen_timestamp
ORDER BY created_at DESC
LIMIT 20;
```

---

#### 4.4 Solution 3: Materialized Unread Count

Instead of `COUNT(*)` on every page load, maintain a denormalized counter:

```sql
ALTER TABLE students ADD COLUMN unread_count INTEGER DEFAULT 0;
```

- Increment on new notification insert
- Decrement on mark-as-read
- Zero out on mark-all-as-read

**Tradeoffs:**

| Advantage | Disadvantage |
|-----------|--------------|
| O(1) count lookup | Counter can drift if updates fail — needs periodic reconciliation |
| No COUNT(*) query needed | Additional write on every notification event |
| Instantly available for badge display | Slightly more complex application logic |

---

#### 4.5 Solution 4: Connection Pooling

Use PgBouncer or built-in connection pooling to manage DB connections efficiently:

```
Application → PgBouncer (pool) → PostgreSQL
```

**Tradeoffs:**

| Advantage | Disadvantage |
|-----------|--------------|
| Reuses DB connections (avoids overhead of new connections) | Extra component to manage |
| Limits concurrent connections to DB | Transaction mode may not support all features |
| Handles connection spikes gracefully | — |

---

#### 4.6 Recommended Architecture

```
Client → API → Redis Cache (L1)
                    ↓ (miss)
               PostgreSQL Read Replica (L2)
                    ↓ (write)
               PostgreSQL Primary (L3)
```

---

## Stage 5

### Bulk Notification Redesign

#### 5.1 Problems with the Current Implementation

```python
function notify_all(student_ids: array, message: string):
    for student_id in student_ids:
        send_email(student_id, message)  # calls Email API
        save_to_db(student_id, message)  # DB insert
        push_to_app(student_id, message) # real-time push
```

| Problem | Explanation |
|---------|-------------|
| **Sequential processing** | Processes 50,000 students one at a time. If each email takes 200ms, total time = 50,000 × 0.2s = **2.8 hours**. The HR is waiting 3 hours for "Notify All" to complete. |
| **No error handling** | If `send_email` fails for student #25,001, there's no retry. The email is lost. 200 students got no email and nobody knows which ones. |
| **No partial failure recovery** | If the process crashes at student #30,000, there's no way to resume from where it left off. Running it again sends duplicate emails to the first 30,000. |
| **Tight coupling** | Email, DB write, and push notification are synchronous and coupled. If the email API is slow, it blocks DB writes and push notifications too. |
| **No idempotency** | Re-running after a failure sends duplicate notifications to students already processed. |
| **Single point of failure** | Runs on one server. If that server goes down, everything stops. |
| **No rate limiting** | Blasting 50,000 emails at once will likely trigger the email provider's rate limit, causing failures. |

---

#### 5.2 What Happened: 200 Emails Failed Midway

When `send_email` failed for 200 students:

1. **Those 200 students never got the email** — and there's no record of which ones failed.
2. **DB writes and push notifications may or may not have happened** for those students, depending on whether the failures were before or after those calls.
3. **We can't simply re-run** the function because students who already received emails would get duplicates.

**To recover**, we would need to:
- Identify the 200 failed student IDs (impossible without logs)
- Manually retry only those students
- This is operationally painful and error-prone

---

#### 5.3 Should DB Save and Email Happen Together?

**No, they should NOT happen in the same transaction.** Reasons:

1. **Different failure modes**: DB writes are local (fast, reliable). Email is a network call to an external API (slow, unreliable). Coupling them means a slow email API blocks DB writes.

2. **Different SLAs**: The in-app notification (DB write) should appear instantly. The email can arrive within minutes — users expect this delay.

3. **Rollback complexity**: If the email fails, should we rollback the DB insert? No — the student should still see the in-app notification even if the email is delayed.

**Use eventual consistency:** Save to DB first (guaranteed), then enqueue the email as a separate async task. If the email fails, retry it independently without affecting the DB record.

---

#### 5.4 Redesigned Solution

**Architecture: Queue-based fan-out with independent workers**

```
HR clicks "Notify All"
        ↓
  API creates a Batch Job (status: PENDING)
        ↓
  Batch Job splits 50,000 students into chunks of 500
        ↓
  Each chunk → Message Queue (RabbitMQ/Kafka)
        ↓
  Worker Pool consumes chunks in parallel:
    ├── Worker 1: students 1-500
    ├── Worker 2: students 501-1000
    ├── ...
    └── Worker 100: students 49,501-50,000
        ↓
  Each worker per student:
    1. save_to_db()          ← Fast, reliable
    2. push_to_app()         ← SSE push
    3. enqueue_email()       ← Separate email queue
        ↓
  Email Worker Pool:
    - Consumes from email queue
    - Sends email with rate limiting
    - On failure: retry with exponential backoff (max 5 retries)
    - On permanent failure: move to Dead Letter Queue
```

**Revised pseudocode:**

```python
# Step 1: API endpoint - returns immediately
async def notify_all(student_ids: list, message: str) -> dict:
    batch_id = generate_uuid()
    
    # Record the batch job
    save_batch_job(batch_id, status="PROCESSING", total=len(student_ids))
    
    # Split into chunks and enqueue
    chunks = split_into_chunks(student_ids, chunk_size=500)
    for chunk in chunks:
        enqueue_to_message_broker(
            queue="notification.process",
            payload={
                "batch_id": batch_id,
                "student_ids": chunk,
                "message": message
            }
        )
    
    # Return immediately - don't make HR wait
    return {"batch_id": batch_id, "status": "PROCESSING", "total": len(student_ids)}


# Step 2: Worker processes each chunk
async def process_notification_chunk(payload: dict):
    batch_id = payload["batch_id"]
    student_ids = payload["student_ids"]
    message = payload["message"]
    
    for student_id in student_ids:
        idempotency_key = f"{batch_id}:{student_id}"
        
        # Skip if already processed (idempotency check)
        if is_already_processed(idempotency_key):
            continue
        
        try:
            # Step 2a: Save to DB (fast, reliable)
            notification_id = save_to_db(student_id, message)
            
            # Step 2b: Push real-time notification via SSE
            push_to_app(student_id, notification_id)
            
            # Step 2c: Enqueue email separately
            enqueue_to_message_broker(
                queue="email.send",
                payload={
                    "student_id": student_id,
                    "message": message,
                    "idempotency_key": idempotency_key,
                    "attempt": 1
                }
            )
            
            # Mark as processed for idempotency
            mark_as_processed(idempotency_key)
            
        except Exception as e:
            log_error(f"Failed for student {student_id}: {e}")
            # Don't stop — continue processing other students
    
    update_batch_progress(batch_id, processed=len(student_ids))


# Step 3: Email worker with retry logic
async def send_email_worker(payload: dict):
    student_id = payload["student_id"]
    attempt = payload["attempt"]
    max_retries = 5
    
    try:
        send_email(student_id, payload["message"])
        mark_email_sent(payload["idempotency_key"])
        
    except TemporaryError as e:
        if attempt < max_retries:
            # Retry with exponential backoff
            delay = 2 ** attempt  # 2s, 4s, 8s, 16s, 32s
            enqueue_with_delay(
                queue="email.send",
                payload={**payload, "attempt": attempt + 1},
                delay_seconds=delay
            )
        else:
            # Move to Dead Letter Queue for manual review
            move_to_dlq("email.dlq", payload, error=str(e))
    
    except PermanentError as e:
        # Don't retry — move to DLQ immediately
        move_to_dlq("email.dlq", payload, error=str(e))
```

**Key improvements:**

| Feature | Old | New |
|---------|-----|-----|
| Processing | Sequential (2.8 hours) | Parallel workers (~30 seconds) |
| Error handling | None | Per-student try/catch, continues on failure |
| Email failures | Lost forever | Retry with backoff, DLQ for permanent failures |
| Idempotency | None (duplicates on re-run) | Idempotency key prevents duplicates |
| User experience | HR waits hours | API returns immediately, progress tracked async |
| Scalability | Single server | Horizontally scalable worker pool |
| Recovery | Impossible | Resume from any point using message queue |

---

## Stage 6

### Priority Inbox

#### 6.1 Problem Statement

Display the top N most important unread notifications, where priority is determined by:
1. **Type weight**: Placement (weight 3) > Result (weight 2) > Event (weight 1)
2. **Recency**: More recent notifications rank higher

#### 6.2 Algorithm Design

**Priority Score Formula:**

```
priority_score = type_weight × 1000 + recency_score
```

Where:
- `type_weight` = `{Placement: 3, Result: 2, Event: 1}`
- `recency_score` = Unix timestamp of the notification (higher = more recent)

Multiplying `type_weight` by 1000 ensures type always dominates, but within the same type, recency determines order. Actually, since timestamps are large numbers (Unix epoch), we use:

```
priority_score = type_weight * 10^12 + unix_timestamp
```

This ensures Placement notifications always rank above Result notifications, regardless of timing.

#### 6.3 Data Structure: Min-Heap of Size N

To efficiently maintain the top N notifications:

1. Use a **min-heap** of size N (sorted by priority score ascending).
2. For each incoming notification:
   - If heap size < N → push it in.
   - If notification's score > heap's minimum → pop the minimum, push the new one.
   - Otherwise → skip it (not in top N).

**Time complexity:**
- Initial build: O(M × log N) where M = total notifications
- Each new notification: O(log N)
- Retrieve top N: O(N × log N) for sorted output

This is optimal for maintaining a running top-N as new notifications arrive.

#### 6.4 Implementation

The implementation is in `notification_app_be/priority_inbox.py`, which:
1. Fetches notifications from the evaluation service API.
2. Computes priority scores.
3. Uses a min-heap to extract the top 10.
4. Returns them sorted by priority (highest first).

The FastAPI endpoints are at:
- `GET /notifications` — fetch raw notifications from the test server.
- `GET /notifications/priority?n=10` — returns the top N priority-sorted notifications.

New notifications can be ingested efficiently: each new notification is compared against the heap's minimum in O(log N) time, maintaining the top N without re-sorting the entire collection.
