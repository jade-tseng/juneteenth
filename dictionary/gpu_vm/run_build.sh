#!/usr/bin/env bash
# Run ON the GPU VM after setup.sh. Pulls reference videos from the dictionary
# bucket, runs real SMPLer-X extraction for every manifest entry, schema-
# validates, and uploads the clips back to GCS for W3 to read.
set -euo pipefail

cd "$(dirname "$0")/.."

BUCKET=${BUCKET:-gs://buildday-499318-dictionary}
VIDEOS=${VIDEOS:-./raw}

if [ -z "${SMPLERX_INFER:-}" ]; then
  echo "SMPLERX_INFER is unset — run gpu_vm/setup.sh and export it first." >&2
  exit 1
fi

echo ">> Fetching reference videos from ${BUCKET}/raw"
mkdir -p "$VIDEOS"
gsutil -m rsync -r "${BUCKET}/raw" "$VIDEOS"

echo ">> Extracting (SMPLer-X -> clean -> validated SMPLXClip)"
python build.py extract --videos "$VIDEOS" --src-fps "${SRC_FPS:-30}"
python build.py validate

echo ">> Uploading clips to ${BUCKET}/clips"
python build.py upload

echo ">> Done. Remember to delete this VM (no GPU at serving time)."
