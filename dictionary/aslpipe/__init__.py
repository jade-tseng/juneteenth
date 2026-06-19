"""W6 dictionary build pipeline for the Voice-to-ASL Signing Avatar POC.

Produces §3.2 SMPLXClips for the §5 seed vocabulary and writes them to the GCS
dictionary bucket. Two paths:
  * real        — SMPLer-X extraction on a GPU VM  (extract -> clean -> build)
  * placeholder — procedural synthesis off-GPU       (synthesize -> build)
Both go through build_clip.build_clip(), which schema-validates before writing.
"""
