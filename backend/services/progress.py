"""Progress tracking for background uploads."""

from datetime import datetime

# Global progress tracking for background uploads
_upload_progress: dict[str, dict] = {}


def update_progress(file_hash: str, status: str, progress: int, message: str, details: dict | None = None):
    """Update upload progress for SSE streaming."""
    _upload_progress[file_hash] = {
        "status": status,  # "processing", "complete", "error"
        "progress": progress,  # 0-100
        "message": message,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
    }
    print(f"[PROGRESS] {file_hash[:8]}... → {progress}% - {message}")


def get_progress(file_hash: str) -> dict | None:
    """Get current upload progress."""
    return _upload_progress.get(file_hash)


def clear_progress(file_hash: str):
    """Clear progress data after completion."""
    if file_hash in _upload_progress:
        del _upload_progress[file_hash]
