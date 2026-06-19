"""Clip storage backends for the dictionary (W3).

The dictionary lives in the GCS `dictionary` bucket as one validated SMPLXClip
JSON per entry. A local backend mirrors the same layout for dev/tests (e.g. the
renderer's stub clips) before W6 lands real clips.
"""

from __future__ import annotations

import abc
import json
from pathlib import Path

from asl_schemas import SMPLXClip


class ClipStore(abc.ABC):
    @abc.abstractmethod
    def load_all(self) -> list[SMPLXClip]:
        """Load and schema-validate every clip in the dictionary."""


class LocalClipStore(ClipStore):
    """Reads *.json clips from a local directory (dev / tests)."""

    def __init__(self, directory: str | Path):
        self._dir = Path(directory)

    def load_all(self) -> list[SMPLXClip]:
        clips: list[SMPLXClip] = []
        for path in sorted(self._dir.glob("*.json")):
            clips.append(SMPLXClip.model_validate_json(path.read_text()))
        return clips


class GCSClipStore(ClipStore):
    """Reads clips from gs://<bucket>/<prefix>*.json."""

    def __init__(self, bucket: str, prefix: str = "clips/", client=None):
        self._bucket = bucket
        self._prefix = prefix
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google.cloud import storage  # lazy import

            self._client = storage.Client()
        return self._client

    def load_all(self) -> list[SMPLXClip]:
        client = self._get_client()
        clips: list[SMPLXClip] = []
        for blob in client.list_blobs(self._bucket, prefix=self._prefix):
            if not blob.name.endswith(".json"):
                continue
            data = json.loads(blob.download_as_text())
            clips.append(SMPLXClip.model_validate(data))
        return clips
