# Real ASL clips — turnkey runbook (W6, real-data path)

The seed dictionary currently ships **synthetic placeholder clips**
(`build.py synth`, stamped `extractor=synthetic-placeholder`). This document is
the exact procedure to replace them with **real, recognizable ASL** for the 13
lexical seed words (§5). All ingestion code is built and unit-tested; what
remains is gated on external resources you cannot obtain in CI:

- a **GPU VM + GPU quota** (L4/T4),
- **WLASL video downloads** (third-party hosting, route A), and/or
- **SignAvatars dataset approval** (Google Form, route B).

Pick **route A (WLASL + SMPLer-X)** or **route B (SignAvatars `.pkl`)**. Route B
gives cleaner motion (mocap-grade SMPL-X, no estimation) but needs form
approval; route A needs only a GPU. Either way the output is identical:
schema-valid `SMPLXClip` JSON in `gs://buildday-499318-dictionary/clips/`.

Fingerspelling (J/A/D/E/I) is **descoped for v1**; both routes cover the 13
lexical words only.

---

## Gloss → clip_id selection mapping

`clip_id` follows `manifest.json` (`{gloss_lower}-001`). W3 lookup resolves on
`gloss`, so the clip filename is stable regardless of which source video backs it.

| Seed gloss | clip_id | WLASL gloss | Notes |
|---|---|---|---|
| HELLO | `hello-001` | hello | |
| HOW | `how-001` | how | |
| YOU | `you-001` | you | |
| TODAY | `today-001` | today | |
| MY | `my-001` | my | |
| NAME | `name-001` | name | |
| ME | `me-001` | me | (W3 synonym map also routes I↔ME) |
| SIGN | `sign-001` | sign | |
| NOT | `not-001` | not | |
| BUT | `but-001` | but | |
| CAN | `can-001` | can | |
| HAPPY | `happy-001` | happy | |
| **COMMUNICATE** | `communicate-001` | **talk** | **synonym — see below** |

### COMMUNICATE synonym decision

**COMMUNICATE is not a WLASL gloss.** Decision: back `communicate-001` with the
WLASL/SignAvatars sign for **TALK** (synonym preference order in
`aslpipe/wlasl.py::SYNONYMS`: `talk → communication → interact`). The clip keeps
`gloss="COMMUNICATE"` and `clip_id="communicate-001"` so the §5 demo script
resolves unchanged. `build.py wlasl-select` marks it with `synonym_of: "talk"`
in the selection manifest for traceability. If no synonym is present in the
metadata, it is reported under `missing` and can be omitted from v1.

Run `python build.py wlasl-select` to (re)generate the concrete mapping with
the real video IDs into `dictionary/wlasl_selection.json`.

---

## Route A — WLASL + SMPLer-X on a GPU VM

### A1. Select source videos (off-GPU, no downloads)
```bash
cd dictionary
# fetches WLASL_v0.3.json metadata (small JSON; NOT the videos) and picks one
# preferred instance per seed gloss -> wlasl_selection.json
python build.py wlasl-select
#   or with a local metadata file:
#   python build.py wlasl-select --metadata /path/WLASL_v0.3.json
```
Review `wlasl_selection.json`: each entry has `video_id`, `url`, `split`. These
are the only videos to download. Selection prefers non-`test` split + a
reasonable length; override by hand-editing the manifest if a clip is bad.

### A2. Download exactly the selected videos → `raw/`
WLASL videos are third-party hosted (YouTube/aslpro/etc.); use the WLASL
`start_kit` downloader against your `wlasl_selection.json` `url`s, naming each
file `<clip_id>.mp4` so it matches `manifest.json`'s `video` field
(`hello.mp4`, …) — or update `manifest.json` `video` fields to the downloaded
names. Upload to the bucket so the VM can pull them:
```bash
gsutil -m cp raw/*.mp4 gs://buildday-499318-dictionary/raw/
```
> Licensing (§11): WLASL clips are aggregated under non-commercial terms; **POC
> only**. Do not ship commercially without re-clearing source rights.

### A3. Enable GPU + provision the VM
```bash
gcloud services enable compute.googleapis.com --project=buildday-499318
# Ensure L4 (or T4) quota in the target region; request an increase if needed:
#   Console → IAM & Admin → Quotas → "NVIDIA L4 GPUs" / "GPUS_ALL_REGIONS"
bash gpu_vm/provision.sh        # creates an L4 spot VM (T4 alt in the script)
```

### A4. Extract → clean → build → validate → upload (on the VM)
```bash
gcloud compute scp --zone=us-central1-a --recurse . smplx-extract:~/dictionary
gcloud compute ssh --zone=us-central1-a smplx-extract -- \
  'cd dictionary && bash gpu_vm/setup.sh'   # installs SMPLer-X; prints licensed downloads
# perform the 2 manual licensed downloads setup.sh prints (SMPL-X model +
# SMPLer-X checkpoint), then export SMPLERX_INFER, then:
gcloud compute ssh --zone=us-central1-a smplx-extract -- \
  'cd dictionary && bash gpu_vm/run_build.sh'
```
`run_build.sh` runs `build.py extract` →
`aslpipe/extract.py` (SMPLer-X, **full 45-dim hands, not PCA**) →
`aslpipe/clean.py::clean_frames` (**normalize_root** → trim → smooth → resample
24/25→30fps → rest-pad) → `build_clip` (schema-validate) →
`upload_clips` to `gs://buildday-499318-dictionary/clips/`.

### A5. Tear down (serving-cost gotcha — no GPU at runtime)
```bash
gcloud compute instances delete smplx-extract --zone=us-central1-a --project=buildday-499318
```

---

## Route B — SignAvatars `.pkl` (no GPU needed)

SignAvatars ships per-sign SMPL-X parameter sequences (182-dim: root3, body63,
lhand45, rhand45 [**full** hands], jaw3, betas10, expr10, transl3 @ 24fps).
Conversion is pure CPU — no estimation, no GPU.

### B1. Get the data (gated)
Submit the SignAvatars access request:
<https://signavatars.github.io/> → **Download / Google Form**. Approval is
manual and non-commercial (§11). On approval, download the SMPL-X `.pkl`
sequences for the seed signs (use TALK for COMMUNICATE).

### B2. Stage the pkls → `<clip_id>.pkl`
Name each sequence by its target clip_id so it matches `manifest.json`:
```
pkls/hello-001.pkl  pkls/how-001.pkl  …  pkls/communicate-001.pkl  (= talk)
```

### B3. Convert → validate → upload (off-GPU)
```bash
cd dictionary
python build.py signavatars pkls/    # convert_dir: load → clean_frames(24→30) → build → write
python build.py validate             # frozen-contract schema check (same as CI)
python build.py upload               # rsync clips/ → gs://buildday-499318-dictionary/clips/
```
`build.py signavatars` runs `aslpipe/signavatars.py::convert_dir`, which for
each entry: loads the pkl → `frames_from_params` (handles dict-of-arrays *or*
flat (T,182)) → `clean_frames(src_fps=24, dst_fps=30)` (incl. `normalize_root`)
→ `build_clip` (schema-validate) → `write_clip`. Only `kind=="lexical"` entries
are processed (fingerspelling descoped).

> Licensing (§11): SignAvatars is **non-commercial**; POC only.

---

## Coordinate normalization (why it matters)

Both routes produce **camera-frame** poses: `global_orient`/`transl` are
relative to the capture camera, so fed raw to the renderer (W5) the avatar comes
out **rotated and off-screen**. `clean_frames` now runs
`posekit.normalize_root` first (on by default): it removes frame 0's root
rotation (front-faces the avatar, preserving any in-sign torso turn as motion
*relative* to frame 0) and re-centers `transl` to the origin. Local body/hand/
jaw poses are untouched. Disable with `clean_frames(..., normalize=False)` if a
source is already canonicalized.

---

## Verification (post-upload)

1. `python build.py validate` → all clips schema-valid (frozen `SMPLXClip`).
2. Load each clip in the W5b player; confirm it is **front-facing, centered**,
   hands + jaw move, and the sign is recognizable.
3. ASL-literate spot-check (§12 definition of done).
4. Swap any bad extraction by hand-picking a different WLASL instance (edit
   `wlasl_selection.json`) or a different SignAvatars take, then re-run that
   clip only (`build.py extract --only <clip_id>` for route A).

## Code status

| Piece | Status |
|---|---|
| `aslpipe/wlasl.py` — metadata parse + per-gloss selection | code-complete, unit-tested |
| `aslpipe/signavatars.py` — `.pkl` → SMPLXClip converter | code-complete, unit-tested (synthetic pkl) |
| `posekit.normalize_root` + `clean_frames(normalize=...)` | code-complete, unit-tested |
| `build.py wlasl-select` / `build.py signavatars` | wired, `--help` works |
| Actual real clips | **gated**: GPU/quota (A), video downloads (A), SignAvatars form (B) |
