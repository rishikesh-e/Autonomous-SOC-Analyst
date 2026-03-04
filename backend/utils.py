"""
Utility functions for the SOC Analyst backend
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get the current UTC time as a timezone-aware datetime.
    """
    return datetime.now(timezone.utc)


def utc_isoformat() -> str:
    """
    Get the current UTC time as an ISO 8601 formatted string with 'Z' suffix.

    This ensures consistency across the system:
    - Backend generates timestamps with 'Z' suffix
    - Fluent-bit expects 'Z' suffix in Time_Format
    - Elasticsearch stores as proper UTC timestamps
    - Frontend can parse consistently

    Returns:
        str: ISO 8601 formatted timestamp, e.g., '2024-02-24T10:30:45.123456Z'
    """
    # Replace +00:00 with Z for proper ISO 8601 UTC representation
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def to_utc_isoformat(dt: datetime) -> str:
    """
    Convert a datetime object to an ISO 8601 formatted string with 'Z' suffix.

    Args:
        dt: A datetime object (will be treated as UTC if not timezone-aware)

    Returns:
        str: ISO 8601 formatted timestamp with 'Z' suffix
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to UTC and format
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.isoformat().replace('+00:00', 'Z')
