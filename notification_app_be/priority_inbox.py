"""
Priority Inbox Algorithm

Uses a min-heap to efficiently maintain the top N most important
notifications. Priority is determined by type weight and recency.

Priority Score = type_weight * 10^12 + unix_timestamp

This ensures:
  - Placement (weight 3) always ranks above Result (weight 2)
  - Result (weight 2) always ranks above Event (weight 1)
  - Within the same type, more recent notifications rank higher
"""

import heapq
from datetime import datetime

# Type weights: Placement > Result > Event
TYPE_WEIGHTS = {
    "Placement": 3,
    "Result": 2,
    "Event": 1,
}

WEIGHT_MULTIPLIER = 10**12


def compute_priority_score(notification: dict) -> float:
    """
    Compute a priority score for a notification.

    Score = type_weight * 10^12 + unix_timestamp

    Higher score = higher priority.
    """
    notification_type = notification.get("Type", "Event")
    weight = TYPE_WEIGHTS.get(notification_type, 1)

    timestamp_str = notification.get("Timestamp", "")
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        unix_ts = dt.timestamp()
    except (ValueError, TypeError):
        unix_ts = 0.0

    return weight * WEIGHT_MULTIPLIER + unix_ts


class PriorityInbox:
    """
    Maintains the top N notifications using a min-heap.

    - Insertion: O(log N) per notification
    - Retrieval: O(N log N) for sorted top-N output
    """

    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self._heap: list[tuple[float, int, dict]] = []
        self._counter = 0  # Tiebreaker for equal scores

    def push(self, notification: dict) -> None:
        """
        Add a notification to the priority inbox.

        If the inbox is full and this notification has a higher priority
        than the current minimum, it replaces the minimum.
        """
        score = compute_priority_score(notification)
        entry = (score, self._counter, notification)
        self._counter += 1

        if len(self._heap) < self.capacity:
            heapq.heappush(self._heap, entry)
        elif score > self._heap[0][0]:
            heapq.heapreplace(self._heap, entry)

    def get_top_n(self) -> list[dict]:
        """
        Return the top N notifications sorted by priority (highest first).

        Each notification is enriched with its computed priority_score
        and rank.
        """
        sorted_items = sorted(self._heap, key=lambda x: x[0], reverse=True)

        results = []
        for rank, (score, _, notification) in enumerate(sorted_items, start=1):
            results.append({
                "rank": rank,
                "priority_score": score,
                "type_weight": TYPE_WEIGHTS.get(notification.get("Type", "Event"), 1),
                **notification,
            })

        return results

    def size(self) -> int:
        """Current number of notifications in the inbox."""
        return len(self._heap)

    def clear(self) -> None:
        """Clear all notifications from the inbox."""
        self._heap.clear()
        self._counter = 0


def get_top_n_notifications(notifications: list[dict], n: int = 10) -> list[dict]:
    """
    Convenience function: given a list of notifications, return the top N
    by priority using a min-heap.

    Args:
        notifications: List of notification dicts with Type, Message, Timestamp.
        n: Number of top notifications to return.

    Returns:
        List of top N notifications sorted by priority (highest first).
    """
    inbox = PriorityInbox(capacity=n)

    for notification in notifications:
        inbox.push(notification)

    return inbox.get_top_n()
