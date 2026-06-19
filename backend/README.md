# backend — Cloud Run service (gloss / lookup / blend)

POC backend for the Voice-to-ASL Signing Avatar. Currently implements **W2 — the
gloss step** (§4.2). Lookup (W3), blend (W4), and the `/api/sign` wiring land here
later. Imports the frozen contracts from `schemas/python` (`asl_schemas`).

## W2 — gloss step (English → `GlossSequence`)

`app/gloss/` turns an English string into a `GlossSequence` (§3.3) through a
fall-through chain — the first provider that yields valid tokens wins, and the
terminal passthrough is always available, so it never hard-fails:

```
cache (verified demo script)  →  Nebius (primary)  →  Claude (fallback)  →  passthrough
```

| Provider | File | Notes |
|---|---|---|
| Demo cache | `cache.py` | The 5 §5 script lines, hand-verified — the live demo never depends on an LLM call |
| Nebius (primary) | `nebius.py` | OpenAI-compatible SDK, `NEBIUS_API_KEY` |
| Claude (fallback) | `claude.py` | Anthropic SDK, `ANTHROPIC_API_KEY` |
| Passthrough | `passthrough.py` | Deterministic, offline; drops articles/copula, fingerspells proper nouns |

```python
from app.gloss import GlossService
svc = GlossService()
svc.to_gloss("My name is Jade.").gloss
# -> ['MY', 'NAME', 'fs:J', 'fs:A', 'fs:D', 'fs:E']  (from cache)
```

### Configuration (env vars)
| Var | Purpose | Default |
|---|---|---|
| `NEBIUS_API_KEY` | Nebius auth | — (provider disabled if unset) |
| `NEBIUS_BASE_URL` | Nebius endpoint | `https://api.studio.nebius.com/v1/` |
| `NEBIUS_MODEL` | Nebius model | `meta-llama/Llama-3.3-70B-Instruct` |
| `ANTHROPIC_API_KEY` | Claude auth | — (provider disabled if unset) |
| `ANTHROPIC_MODEL` | Claude model | `claude-opus-4-8` |

On Cloud Run these come from Secret Manager (`VAPI_API_KEY`, `NEBIUS_API_KEY`,
`ANTHROPIC_API_KEY`) via the `signing-runtime` service account — see `/infra`.

### Dev
```sh
cd backend
python -m pip install -e ../schemas/python   # frozen contracts
python -m pip install -e ".[dev]"
python -m pytest -q                           # offline: cache + passthrough + fall-through

# live LLM smoke test (uses the real Nebius key)
export NEBIUS_API_KEY="$(gcloud secrets versions access latest --secret=NEBIUS_API_KEY --project=buildday-499318)"
python -c "from app.gloss import GlossService; print(GlossService(use_cache=False).to_gloss('Thank you very much.').gloss)"
```

## Status / next
- ✅ **W2** gloss step — cache + Nebius + Claude + passthrough, verified live
- ⬜ **W3** dictionary lookup (reads GCS `dictionary` bucket) — needs W6 clips
- ⬜ **W4** concatenate + slerp blend
- ⬜ **API** `POST /api/sign` wiring W2→W3→W4 on Cloud Run
