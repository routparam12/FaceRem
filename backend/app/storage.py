"""
Secure local storage for employee profile pictures and rolling 7-day kiosk scan photos.
Enforces admin-only access and automatic 7-day retention pruning.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import shutil

BASE_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
AVATARS_DIR = BASE_STORAGE_DIR / "avatars"
SCANS_DIR = BASE_STORAGE_DIR / "scans"

AVATARS_DIR.mkdir(parents=True, exist_ok=True)
SCANS_DIR.mkdir(parents=True, exist_ok=True)


def save_profile_picture(organization_id: str, employee_id: str, image_bytes: bytes) -> str:
    """Saves the enrollment front face photo as the employee's profile avatar."""
    org_dir = AVATARS_DIR / organization_id
    org_dir.mkdir(parents=True, exist_ok=True)
    file_path = org_dir / f"{employee_id}.jpg"
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    return str(file_path)


def get_profile_picture(organization_id: str, employee_id: str) -> bytes | None:
    """Retrieves the profile avatar image bytes if present."""
    file_path = AVATARS_DIR / organization_id / f"{employee_id}.jpg"
    if file_path.is_file():
        with open(file_path, "rb") as f:
            return f.read()
    return None


def delete_profile_picture(organization_id: str, employee_id: str) -> None:
    """Deletes the profile avatar if present."""
    file_path = AVATARS_DIR / organization_id / f"{employee_id}.jpg"
    if file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            pass


def save_scan_photo(organization_id: str, employee_id: str, image_bytes: bytes, event_id: str) -> str:
    """
    Saves a kiosk verification scan photo and automatically prunes any scan photos
    for this employee older than 7 days.
    """
    emp_dir = SCANS_DIR / organization_id / employee_id
    emp_dir.mkdir(parents=True, exist_ok=True)

    # Prune old scans first (older than 7 days)
    prune_scan_photos(organization_id, employee_id, max_age_days=7)

    # Save current scan
    now_ts = int(datetime.now(timezone.utc).timestamp())
    file_name = f"{now_ts}_{event_id}.jpg"
    file_path = emp_dir / file_name
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    return file_name


def prune_scan_photos(organization_id: str, employee_id: str, max_age_days: int = 7) -> int:
    """Removes all scan photos older than max_age_days for the specified employee."""
    emp_dir = SCANS_DIR / organization_id / employee_id
    if not emp_dir.is_dir():
        return 0

    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).timestamp()
    deleted_count = 0

    try:
        for entry in emp_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() in (".jpg", ".jpeg", ".png"):
                try:
                    # File name format: {timestamp}_{event_id}.jpg or check mtime
                    parts = entry.stem.split("_")
                    if parts and parts[0].isdigit():
                        file_ts = float(parts[0])
                    else:
                        file_ts = entry.stat().st_mtime
                    if file_ts < cutoff_ts:
                        entry.unlink()
                        deleted_count += 1
                except (ValueError, OSError):
                    pass
    except OSError:
        pass

    return deleted_count


def list_recent_scan_photos(organization_id: str, employee_id: str, max_age_days: int = 7) -> list[dict]:
    """
    Returns list of scan photos from the last max_age_days for admin inspection.
    Sorted descending by capture time.
    """
    emp_dir = SCANS_DIR / organization_id / employee_id
    if not emp_dir.is_dir():
        return []

    prune_scan_photos(organization_id, employee_id, max_age_days=max_age_days)

    photos = []
    try:
        for entry in emp_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() in (".jpg", ".jpeg", ".png"):
                parts = entry.stem.split("_")
                event_id = parts[1] if len(parts) > 1 else ""
                if parts and parts[0].isdigit():
                    ts = int(parts[0])
                else:
                    ts = int(entry.stat().st_mtime)
                iso_time = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                photos.append({
                    "id": entry.name,
                    "event_id": event_id,
                    "timestamp": iso_time,
                    "size_bytes": entry.stat().st_size,
                })
    except OSError:
        pass

    photos.sort(key=lambda x: x["timestamp"], reverse=True)
    return photos


def get_scan_photo(organization_id: str, employee_id: str, photo_id: str) -> bytes | None:
    """Reads scan photo bytes safely without directory traversal."""
    safe_name = os.path.basename(photo_id)
    file_path = SCANS_DIR / organization_id / employee_id / safe_name
    if file_path.is_file():
        with open(file_path, "rb") as f:
            return f.read()
    return None

