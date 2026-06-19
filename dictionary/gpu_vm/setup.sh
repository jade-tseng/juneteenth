#!/usr/bin/env bash
# Run ON the GPU VM. Installs SMPLer-X + this pipeline's deps and fetches the
# SMPL-X model assets and the SMPLer-X checkpoint. Exports SMPLERX_INFER so
# aslpipe.extract can find the inference entrypoint.
set -euo pipefail

cd "$(dirname "$0")/.."

echo ">> Python deps for the build pipeline"
pip install -r requirements.txt
pip install -e ../schemas/python   # asl_schemas (frozen contracts, for validation)

echo ">> Clone SMPLer-X (OSX-class whole-body SMPL-X estimator)"
SMPLERX_DIR=${SMPLERX_DIR:-$HOME/SMPLer-X}
if [ ! -d "$SMPLERX_DIR" ]; then
  git clone https://github.com/caizhongang/SMPLer-X.git "$SMPLERX_DIR"
fi
pip install -r "$SMPLERX_DIR/requirements.txt" || true

cat <<'NOTE'
>> MANUAL STEPS (licensed downloads — cannot be scripted):
   1. SMPL-X model assets (SMPLX_NEUTRAL.npz) from https://smpl-x.is.tue.mpg.de
      — research/non-commercial only (CLAUDE.md §11). Place under
      $SMPLERX_DIR/common/utils/human_model_files/smplx/.
   2. SMPLer-X pretrained checkpoint (e.g. smpler_x_h32.pth.tar) per its README,
      into $SMPLERX_DIR/pretrained_models/.

>> Then export the inference entrypoint so extract.py can call it:
   export SMPLERX_INFER="$SMPLERX_DIR/main/inference.py"
   (add to ~/.bashrc; adjust the path/flags in aslpipe/extract.py to your fork)
NOTE
