# `/dictionary` — W6 offline dictionary build

Builds the seed ASL dictionary: one `SMPLXClip` (§3.2) per entry in the demo-script
vocabulary (§5), written to the GCS dictionary bucket for **W3 lookup** to read.

```
voice → gloss (W2) → [ dictionary lookup (W3) ] → blend (W4) → player (W5)
                              ▲
                       reads gs://…-dictionary/clips/*.json
                              ▲
                       THIS PIPELINE writes them
```

## Two build paths

| Path | Command | Where | Output |
|------|---------|-------|--------|
| **Real** | `build.py extract --videos raw/` | GPU VM | SMPLer-X-extracted clips |
| **Placeholder** | `build.py synth` | anywhere | procedural clips (no GPU/video) |

Both assemble frames via `aslpipe/build_clip.py`, which **schema-validates against
the frozen `asl_schemas.SMPLXClip` before writing** — the same check CI runs (W0).

### Placeholder clips (current state)

`build.py synth` generates schema-valid clips for all 18 entries with smooth,
rest-padded, *distinct* motion per sign. They are **not accurate ASL** and are
stamped `source.extractor = "synthetic-placeholder"`. Their purpose: unblock W3
(lookup), W4 (concatenate/blend), and W5b (player) so the chain is buildable and
demoable before reference footage + a GPU are available.

One real property is honoured: **`J` is a motion trajectory, not a static pose**
(§4.6) — the I-handshape hand traces a J through the air. Verify:

```bash
python build.py synth && python build.py validate
```

### Real extraction (GPU VM)

```bash
# 1. provision a build-time L4/T4 VM (delete it after — no GPU at serving time)
bash gpu_vm/provision.sh
# 2. on the VM: install SMPLer-X + assets, then build
bash gpu_vm/setup.sh          # + manual licensed downloads it prints
bash gpu_vm/run_build.sh      # rsync raw/ → extract → clean → validate → upload
```

`run_build.sh` calls `build.py extract`, which runs `aslpipe/extract.py`
(SMPLer-X wrapper, full 45-dim hand pose — **not PCA**), then
`aslpipe/clean.py` (trim → smooth → resample → rest-pad), then validates and
uploads. Extraction quality bounds clip quality; manual cleanup is expected, and
`J`'s trajectory must be spot-checked.

## Layout

```
manifest.json        the 18 §5 entries (gloss, kind, source video, license)
build.py             CLI: synth | extract | validate | upload | all
aslpipe/
  posekit.py         SMPL-X joint indices, Frame, slerp-safe smoothing, trim/pad/resample
  synthesize.py      procedural placeholder clips (incl. J motion)
  extract.py         SMPLer-X wrapper (real path, GPU VM)
  clean.py           post-process raw extraction → clip-ready frames
  build_clip.py      assemble + schema-validate SMPLXClip
  gcs.py             rsync clips ↔ gs://…-dictionary
gpu_vm/              provision / setup / run scripts for the build VM
clips/               built clips (gitignored; rebuild with `build.py synth`)
```

## GCS bucket layout

```
gs://buildday-499318-dictionary/
  raw/      reference sign videos       (input to extraction)
  clips/    <clip_id>.json SMPLXClips   (read by W3)
```

## Licensing (§11)

SMPL-X model + How2Sign-class source video are **non-commercial**. Fine for the
POC; gates productization. Placeholder clips carry the manifest's declared
`license` field for traceability.
