"""Progress tracking for background uploads.

This module provides thread-safe progress tracking for background upload tasks
with automatic TTL-based cleanup to prevent memory leaks.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Thread-safe progress tracking with TTL-based cleanup
_upload_progress: dict[str, dict[str, Any]] = {}
_progress_lock = threading.Lock()

# TTL for progress entries (15 minutes)
PROGRESS_TTL_SECONDS = 900


def _cleanup_stale_entries() -> None:
    """Remove progress entries older than TTL."""
    current_time = time.time()
    stale_keys = []

    with _progress_lock:
        for file_hash, data in _upload_progress.items():
            created_at = data.get("_created_at", 0)
            if current_time - created_at > PROGRESS_TTL_SECONDS:
                stale_keys.append(file_hash)

        for key in stale_keys:
            del _upload_progress[key]
            logger.debug(f"Cleaned up stale progress entry: {key[:8]}...")


def update_progress(
    file_hash: str,
    status: str,
    progress: int,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Update upload progress for SSE streaming.

    Args:
        file_hash: Unique identifier for the upload
        status: Current status ("processing", "complete", "error")
        progress: Progress percentage (0-100)
        message: Human-readable status message
        details: Optional additional details
    """
    # Cleanup stale entries periodically (every ~10 updates)
    if len(_upload_progress) > 0 and hash(file_hash) % 10 == 0:
        _cleanup_stale_entries()

    with _progress_lock:
        existing = _upload_progress.get(file_hash, {})
        _upload_progress[file_hash] = {
            "status": status,
            "progress": progress,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
            "_created_at": existing.get("_created_at", time.time()),
        }

    logger.info(f"[PROGRESS] {file_hash[:8]}... → {progress}% - {message}")


def get_progress(file_hash: str) -> dict[str, Any] | None:
    """
    Get current upload progress.

    Args:
        file_hash: Unique identifier for the upload

    Returns:
        Progress data dict or None if not found
    """
    with _progress_lock:
        data = _upload_progress.get(file_hash)
        if data is None:
            return None

        # Return a copy without internal fields
        return {k: v for k, v in data.items() if not k.startswith("_")}


def clear_progress(file_hash: str) -> None:
    """
    Clear progress data after completion.

    Args:
        file_hash: Unique identifier for the upload
    """
    with _progress_lock:
        if file_hash in _upload_progress:
            del _upload_progress[file_hash]
            logger.debug(f"Cleared progress for {file_hash[:8]}...")


def get_all_active_uploads() -> list[str]:
    """
    Get list of all active upload file hashes.

    Returns:
        List of file hashes with active progress tracking
    """
    with _progress_lock:
        return list(_upload_progress.keys())
