"""Cache module for setting up requests-cache with SQLite backend."""
import requests_cache
import os


def setup_cache():
    """Set up requests-cache with SQLite backend.
    
    Returns:
        requests_cache.CachedSession: Configured cache session
    """
    cache_path = os.path.join("data", "http_cache.sqlite")
    session = requests_cache.CachedSession(
        cache_path,
        backend="sqlite",
        expire_after=3600,  # 1 hour
        allowable_codes=[200],
        allowable_methods=["GET", "POST"],
        stale_if_error=True,
    )
    return session


# Create a global cache session
cache_session = setup_cache()