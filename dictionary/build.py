#!/usr/bin/env python3
"""W6 dictionary build CLI.

  python build.py synth                 # procedural placeholder clips (off-GPU)
  python build.py extract --videos DIR  # real SMPLer-X extraction (GPU VM)
  python build.py wlasl-select          # pick WLASL videos -> selection manifest
  python build.py signavatars DIR       # convert SignAvatars .pkl seq -> clips
  python build.py validate              # schema-check every built clip
  python build.py upload                # rsync clips/ -> GCS dictionary bucket
  python build.py all                   # synth + validate (default off-GPU build)

Output clips land in dictionary/clips/<clip_id>.json. Every clip is schema-
validated against the frozen asl_schemas.SMPLXClip before it is written.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIPS_DIR = ROOT / "clips"
MANIFEST = ROOT / "manifest.json"
WLASL_SELECTION = ROOT / "wlasl_selection.json"

# package-local imports
sys.path.insert(0, str(ROOT))
from aslpipe.build_clip import build_clip, write_clip  # noqa: E402
from aslpipe.synthesize import synthesize  # noqa: E402


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def cmd_synth(_args) -> int:
    m = load_manifest()
    fps, raw = m["fps"], m["raw_prefix"]
    built = 0
    for e in m["entries"]:
        frames = synthesize(e["gloss"], e["kind"])
        clip = build_clip(
            clip_id=e["clip_id"], gloss=e["gloss"], kind=e["kind"], fps=fps,
            frames=frames,
            video_url=f"{raw}/{e['video']}",
            license=m["license"],
            extractor="synthetic-placeholder",
        )
        path = write_clip(clip, CLIPS_DIR)
        built += 1
        tag = " (motion)" if e.get("motion") else ""
        print(f"  synth {e['gloss']:<12} -> {path.name}  "
              f"({len(clip['frames'])} frames){tag}")
    print(f"\nBuilt {built} placeholder clips into {CLIPS_DIR}")
    return 0


def cmd_extract(args) -> int:
    from aslpipe.clean import clean_frames
    from aslpipe.extract import extract_video

    m = load_manifest()
    fps = m["fps"]
    videos = Path(args.videos)
    work = ROOT / ".work"
    only = set(args.only) if args.only else None
    built = 0
    for e in m["entries"]:
        if only and e["clip_id"] not in only:
            continue
        video = videos / e["video"]
        if not video.exists():
            print(f"  skip {e['gloss']}: missing {video}", file=sys.stderr)
            continue
        raw_frames = extract_video(video, work / e["clip_id"])
        frames = clean_frames(raw_frames, src_fps=args.src_fps, dst_fps=fps)
        clip = build_clip(
            clip_id=e["clip_id"], gloss=e["gloss"], kind=e["kind"], fps=fps,
            frames=frames,
            video_url=f"{m['raw_prefix']}/{e['video']}",
            license=m["license"], extractor=m["extractor"],
        )
        write_clip(clip, CLIPS_DIR)
        built += 1
        print(f"  extract {e['gloss']:<12} -> {e['clip_id']}.json ({len(frames)} frames)")
    print(f"\nExtracted {built} clip(s) into {CLIPS_DIR}")
    return 0


def cmd_wlasl_select(args) -> int:
    from aslpipe.wlasl import load_metadata, select_for_seed, write_selection

    meta_path = Path(args.metadata) if args.metadata else None
    metadata = load_metadata(meta_path)
    selection = select_for_seed(metadata)
    out = Path(args.out) if args.out else WLASL_SELECTION
    write_selection(selection, out)
    for s in selection["selections"]:
        syn = f"  (synonym: {s['synonym_of']})" if s.get("synonym_of") else ""
        print(f"  {s['gloss']:<12} -> {s['clip_id']}  video={s['video_id']} "
              f"split={s['split']}{syn}")
    if selection["missing"]:
        print(f"\n  MISSING (no WLASL gloss/synonym): {selection['missing']}",
              file=sys.stderr)
    print(f"\nWrote selection manifest -> {out}")
    return 0


def cmd_signavatars(args) -> int:
    from aslpipe.signavatars import convert_dir

    m = load_manifest()
    # SignAvatars covers lexical signs; fingerspelling is descoped for v1.
    entries = [e for e in m["entries"] if e["kind"] == "lexical"]
    written = convert_dir(
        Path(args.pkl_dir), CLIPS_DIR,
        manifest_entries=entries,
        dst_fps=m["fps"], license=m["license"],
    )
    for p in written:
        print(f"  signavatars -> {p.name}")
    print(f"\nConverted {len(written)} SignAvatars clip(s) into {CLIPS_DIR}")
    if not written:
        print("  (no matching <clip_id>.pkl files found in "
              f"{args.pkl_dir})", file=sys.stderr)
        return 1
    return 0


def cmd_validate(_args) -> int:
    # reuse the exact CI validator over the frozen contract
    schemas = ROOT.parent / "schemas" / "python"
    sys.path.insert(0, str(schemas))
    from asl_schemas.validate import validate_file  # noqa: E402

    files = sorted(CLIPS_DIR.glob("*.json"))
    if not files:
        print("no clips to validate; run `synth` or `extract` first", file=sys.stderr)
        return 1
    errors = []
    for f in files:
        errs = validate_file(f, "clip")
        print(f"  [{'OK' if not errs else 'FAIL'}] {f.name}")
        errors.extend(errs)
    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"\nAll {len(files)} clip(s) schema-valid.")
    return 0


def cmd_upload(_args) -> int:
    from aslpipe.gcs import upload_clips
    dest = upload_clips(CLIPS_DIR)
    print(f"Uploaded clips to {dest}")
    return 0


def cmd_all(args) -> int:
    return cmd_synth(args) or cmd_validate(args)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("synth").set_defaults(fn=cmd_synth)

    pe = sub.add_parser("extract")
    pe.add_argument("--videos", required=True, help="dir of reference sign videos")
    pe.add_argument("--src-fps", type=float, default=30.0, help="source video fps")
    pe.add_argument("--only", nargs="*", help="clip_ids to (re)build")
    pe.set_defaults(fn=cmd_extract)

    pw = sub.add_parser("wlasl-select",
                        help="pick one WLASL video per seed gloss -> selection manifest")
    pw.add_argument("--metadata", help="local WLASL_v0.3.json (else fetch upstream)")
    pw.add_argument("--out", help=f"output path (default {WLASL_SELECTION.name})")
    pw.set_defaults(fn=cmd_wlasl_select)

    ps = sub.add_parser("signavatars",
                        help="convert a dir of SignAvatars .pkl SMPL-X sequences -> clips")
    ps.add_argument("pkl_dir", help="dir of <clip_id>.pkl SignAvatars sequences")
    ps.set_defaults(fn=cmd_signavatars)

    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    sub.add_parser("upload").set_defaults(fn=cmd_upload)
    sub.add_parser("all").set_defaults(fn=cmd_all)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
