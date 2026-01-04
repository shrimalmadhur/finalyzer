"""Progress tracking for background uploads."""

from datetime import datetime
from typing import Dict, Optional


# Global progress tracking for background uploads
_upload_progress: Dict[str, Dict] = {}


def update_progress(file_hash: str, status: str, progress: int, message: str, details: Optional[Dict] = None):
    """Update upload progress for SSE streaming."""
    _upload_progress[file_hash] = {
        "status": status,  # "processing", "complete", "error"
        "progress": progress,  # 0-100
        "message": message,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
    }
    print(f"[PROGRESS] {file_hash[:8]}... → {progress}% - {message}")


def get_progress(file_hash: str) -> Optional[Dict]:
    """Get current upload progress."""
    return _upload_progress.get(file_hash)


def clear_progress(file_hash: str):
    """Clear progress data after completion."""
    if file_hash in _upload_progress:
        del _upload_progress[file_hash]
