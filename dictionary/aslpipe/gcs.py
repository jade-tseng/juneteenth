"""GCS I/O for the dictionary bucket via gsutil (no extra Python deps).

Layout in gs://<project>-dictionary:
  raw/    reference sign videos (input to extraction)
  clips/  built SMPLXClip JSON (read by W3 dictionary lookup)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_BUCKET = "gs://buildday-499318-dictionary"


def upload_clips(clips_dir: Path, bucket: str = DEFAULT_BUCKET) -> str:
    """Sync the local clips dir to <bucket>/clips/ (mirrors deletions)."""
    dest = f"{bucket}/clips"
    subprocess.run(
        ["gsutil", "-m", "rsync", "-d", "-r", str(clips_dir), dest], check=True
    )
    return dest


def list_clips(bucket: str = DEFAULT_BUCKET) -> list[str]:
    out = subprocess.run(
        ["gsutil", "ls", f"{bucket}/clips/"],
        capture_output=True, text=True, check=True,
    )
    return [ln for ln in out.stdout.splitlines() if ln.endswith(".json")]
