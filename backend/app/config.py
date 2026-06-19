"""Runtime configuration + clip-store selection.

CLIP_SOURCE selects where the dictionary comes from:
  - "stub"  (default): synthetic §5 seed clips written to a temp dir, read via
            LocalClipStore — lets /api/sign run before W6 lands real clips.
  - "local": LocalClipStore(LOCAL_DICTIONARY_DIR)
  - "gcs":   GCSClipStore(DICTIONARY_BUCKET) — production (W6 clips in GCS)
"""

from __future__ import annotations

import os
import tempfile

from .lookup import ClipStore, GCSClipStore, LocalClipStore
from .stub_dictionary import write_stub_dictionary

DEFAULT_BUCKET = "buildday-499318-dictionary"
TRANSITION_FRAMES = int(os.getenv("BLEND_TRANSITION_FRAMES", "6"))


def clip_store() -> ClipStore:
    source = os.getenv("CLIP_SOURCE", "stub").lower()
    if source == "gcs":
        bucket = os.getenv("DICTIONARY_BUCKET", DEFAULT_BUCKET)
        prefix = os.getenv("DICTIONARY_PREFIX", "clips/")
        return GCSClipStore(bucket, prefix)
    if source == "local":
        return LocalClipStore(os.environ["LOCAL_DICTIONARY_DIR"])
    # stub (default): materialize seed clips into a temp dir for LocalClipStore
    stub_dir = os.getenv("STUB_DICTIONARY_DIR") or tempfile.mkdtemp(prefix="asl-stub-dict-")
    write_stub_dictionary(stub_dir)
    return LocalClipStore(stub_dir)
