import os
import re
import time
import uuid
import tempfile
from pathlib import Path
import pandas as pd


# Configurable default time-to-live for temporary exports: 3600 seconds (1 hour)
DEFAULT_TTL_SECONDS = int(os.environ.get("INSIGHTFORGE_EXPORT_TTL", "3600"))

# Dedicated temporary export directory
EXPORT_DIR = Path(
    os.environ.get("INSIGHTFORGE_EXPORT_DIR")
    or (Path(tempfile.gettempdir()) / "insightforge_clean_exports")
).resolve()

EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Strict validation pattern for download IDs: 16 to 64 alphanumeric characters, hyphens, or underscores
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{16,64}$")

# In-memory registry for download metadata:
# download_id -> { "path": Path, "filename": str, "created_at": float, "ttl": int }
_EXPORTS: dict[str, dict] = {}


def _validate_and_resolve_path(download_id: str) -> Path:
    """
    Validate download ID format and resolve its path safely within EXPORT_DIR.
    Prevents path traversal attacks.
    """
    if not isinstance(download_id, str) or not ID_PATTERN.match(download_id):
        raise ValueError(f"Invalid download ID format: {download_id}")

    target = (EXPORT_DIR / f"{download_id}.csv").resolve()

    # Ensure target path stays strictly inside EXPORT_DIR
    try:
        target.relative_to(EXPORT_DIR)
    except ValueError:
        raise ValueError("Path traversal attempt detected.")

    return target


def sanitize_download_filename(original_filename: str | None = None) -> str:
    """
    Generate a clean, safe, and descriptive download filename like 'original_cleaned.csv'.
    """
    if not original_filename:
        return "cleaned_dataset.csv"

    base = os.path.basename(original_filename.strip())
    base = re.sub(r"\.csv$", "", base, flags=re.IGNORECASE).strip()
    # Remove characters unsafe for filesystems or HTTP headers
    base = re.sub(r'[\\/*?:"<>|\r\n\t]', "", base).strip()

    if not base:
        return "cleaned_dataset.csv"

    return f"{base}_cleaned.csv"


def save_cleaned_export(
    df: pd.DataFrame,
    original_filename: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> tuple[str, str, Path]:
    """
    Export the exact cleaned DataFrame to CSV without index and store in temporary directory.

    Returns:
        (download_id, download_filename, export_path)
    """
    # Proactively clean up expired files before writing new one
    cleanup_expired_exports()

    download_id = uuid.uuid4().hex
    download_filename = sanitize_download_filename(original_filename)
    export_path = _validate_and_resolve_path(download_id)

    # Safe CSV export: index=False guarantees no unwanted DataFrame index column
    # Handles empty DataFrame or 0 columns safely
    df.to_csv(export_path, index=False, encoding="utf-8")

    _EXPORTS[download_id] = {
        "path": export_path,
        "filename": download_filename,
        "created_at": time.time(),
        "ttl": ttl_seconds,
    }

    return download_id, download_filename, export_path


def get_cleaned_export(download_id: str) -> tuple[Path, str]:
    """
    Retrieve export path and download filename for a download ID.
    Raises ValueError if ID format is invalid.
    Raises KeyError if export is missing or expired.
    """
    export_path = _validate_and_resolve_path(download_id)
    now = time.time()

    meta = _EXPORTS.get(download_id)

    if meta is not None:
        if now - meta["created_at"] > meta["ttl"]:
            delete_cleaned_export(download_id)
            raise KeyError(f"Export '{download_id}' has expired.")

        if not export_path.exists():
            delete_cleaned_export(download_id)
            raise KeyError(f"Export file for '{download_id}' is missing on disk.")

        return export_path, meta["filename"]

    # Fallback: check file on disk if server restarted
    if export_path.exists():
        mtime = export_path.stat().st_mtime
        if now - mtime > DEFAULT_TTL_SECONDS:
            export_path.unlink(missing_ok=True)
            raise KeyError(f"Export '{download_id}' has expired.")
        return export_path, f"cleaned_{download_id[:8]}.csv"

    raise KeyError(f"Export '{download_id}' not found.")


def cleanup_expired_exports(max_age_seconds: int | None = None) -> int:
    """
    Removes expired CSV exports from disk and memory.
    Returns the count of purged files.
    """
    now = time.time()
    purged_count = 0

    # 1. Clean in-memory registry
    expired_ids = []
    for d_id, meta in list(_EXPORTS.items()):
        effective_ttl = max_age_seconds if max_age_seconds is not None else meta.get("ttl", DEFAULT_TTL_SECONDS)
        if now - meta["created_at"] > effective_ttl:
            expired_ids.append(d_id)

    for d_id in expired_ids:
        meta = _EXPORTS.pop(d_id, None)
        if meta and meta.get("path"):
            p = meta["path"]
            if isinstance(p, Path) and p.exists():
                try:
                    p.unlink()
                    purged_count += 1
                except OSError:
                    pass

    # 2. Scan disk for orphaned or untracked CSVs older than max_age
    effective_max_age = max_age_seconds if max_age_seconds is not None else DEFAULT_TTL_SECONDS
    try:
        for f in EXPORT_DIR.glob("*.csv"):
            try:
                if now - f.stat().st_mtime > effective_max_age:
                    f.unlink(missing_ok=True)
                    purged_count += 1
            except OSError:
                pass
    except OSError:
        pass

    return purged_count


def delete_cleaned_export(download_id: str) -> bool:
    """
    Explicitly delete an export file and its metadata.
    """
    meta = _EXPORTS.pop(download_id, None)
    deleted = False
    try:
        p = _validate_and_resolve_path(download_id)
        if p.exists():
            p.unlink()
            deleted = True
    except Exception:
        pass
    return deleted or (meta is not None)


def clear_all_exports() -> int:
    """
    Clear all exports in memory and on disk. Used for testing isolation.
    """
    _EXPORTS.clear()
    count = 0
    try:
        for f in EXPORT_DIR.glob("*.csv"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass
    except OSError:
        pass
    return count
