"""Generate canonical JSON Schema (schemas/json/) from the pydantic models.

Run after any change to models.py to keep the language-neutral schema in sync:
    python -m asl_schemas.gen_json_schema
CI also runs this with --check to fail if the committed JSON is stale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .models import GlossSequence, SMPLXClip, SMPLXSequence, VapiTranscriptWebhook

# top-level contracts worth exporting as standalone schema files
_EXPORTS = {
    "smplx_clip": SMPLXClip,
    "smplx_sequence": SMPLXSequence,
    "gloss_sequence": GlossSequence,
    "vapi_webhook": VapiTranscriptWebhook,
}

_OUT_DIR = Path(__file__).resolve().parents[2] / "json"


def _render(model) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in argv

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    stale: list[str] = []
    for name, model in _EXPORTS.items():
        path = _OUT_DIR / f"{name}.schema.json"
        rendered = _render(model)
        if check:
            current = path.read_text() if path.exists() else ""
            if current != rendered:
                stale.append(name)
        else:
            path.write_text(rendered)
            print(f"wrote {path.relative_to(_OUT_DIR.parent)}")

    if check and stale:
        print(f"STALE JSON Schema: {', '.join(stale)} — run gen_json_schema.", file=sys.stderr)
        return 1
    if check:
        print("JSON Schema up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
