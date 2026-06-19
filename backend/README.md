# backend — Cloud Run service (gloss / lookup / blend)

POC backend for the Voice-to-ASL Signing Avatar. Implements the gloss → lookup →
blend pipeline (**W2, W3, W4**); the `/api/sign` Cloud Run wiring lands here next.
Imports the frozen contracts from `schemas/python` (`asl_schemas`).

```
text → [W2 gloss] → GlossSequence → [W3 lookup] → SMPLXClip[] → [W4 blend] → SMPLXSequence
```

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

## W3 — dictionary lookup (`GlossSequence` → `SMPLXClip[]`)
`app/lookup/` resolves each token (lexical or `fs:<letter>`) to a clip, applies a
synonym map (ME↔I), and reports `unmatched`. Clips come from a `ClipStore`:
`GCSClipStore` (the `dictionary` bucket, one validated JSON per clip) in prod,
`LocalClipStore` for dev/tests. A zero-match result → 422 at the API layer (§3.5).

```python
from app.lookup import DictionaryLookup, GCSClipStore
lookup = DictionaryLookup.from_store(GCSClipStore("buildday-499318-dictionary"))
res = lookup.resolve(gloss)        # res.clips, res.unmatched
```

## W4 — concatenate + slerp blend (`SMPLXClip[]` → `SMPLXSequence`)
`app/blend/` blends an ordered clip list into one continuous sequence. Rotation
fields blend **per joint via quaternion slerp** over K transition frames (never
lerp raw axis-angle — §10); expression/transl lerp; clips resample to a common
fps; betas held constant. Optional rest-hold between words.

```python
from app.blend import concatenate
seq = concatenate(res.clips, transition_frames=6)   # one SMPLXSequence
```

## API — `POST /api/sign` (`app/main.py`)
FastAPI app wiring W2→W3→W4. The dictionary loads once at startup from the
configured clip store (`CLIP_SOURCE`, see Configuration).

| Endpoint | Purpose |
|---|---|
| `POST /api/sign` | `{ "text": "..." }` → `SMPLXSequence` (200) or `{ error, unmatched }` (422 on zero matches, §3.5) |
| `POST /api/ingest` | Vapi transcript webhook (§3.4) → same pipeline |
| `GET /healthz` | liveness |

### Clip source (`CLIP_SOURCE`)
| Value | Behavior |
|---|---|
| `stub` (default) | Synthetic §5 seed clips written to a temp dir, read via `LocalClipStore`. Lets the API run before W6. |
| `local` | `LocalClipStore($LOCAL_DICTIONARY_DIR)` |
| `gcs` | `GCSClipStore($DICTIONARY_BUCKET)` — production (real W6 clips) |

> ⚠️ With `CLIP_SOURCE=stub` the poses are **synthetic placeholders** (a small
> per-gloss joint wiggle), not real ASL — they exercise lookup + blend and render
> *something*. Real signing needs W6's clips in the GCS `dictionary` bucket.

### Run locally
```sh
cd backend && python -m pip install -e ../schemas/python && python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080            # CLIP_SOURCE=stub by default
curl -s localhost:8080/api/sign -H 'content-type: application/json' \
  -d '{"text":"How are you doing today?"}' | python -m json.tool | head
```

### Deploy to Cloud Run
Build from the **repo root** (the image needs the `schemas` package in context):
```sh
REGION=us-central1; PROJECT=buildday-499318
IMAGE=$REGION-docker.pkg.dev/$PROJECT/signing-avatar/api:latest
docker build -f backend/Dockerfile -t "$IMAGE" .   # run from repo root
docker push "$IMAGE"

gcloud run deploy signing-api --image="$IMAGE" --project=$PROJECT --region=$REGION \
  --service-account=signing-runtime@$PROJECT.iam.gserviceaccount.com \
  --set-env-vars=CLIP_SOURCE=gcs,DICTIONARY_BUCKET=$PROJECT-dictionary \
  --set-secrets=NEBIUS_API_KEY=NEBIUS_API_KEY:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,VAPI_API_KEY=VAPI_API_KEY:latest \
  --allow-unauthenticated
```
The `signing-runtime` SA already has `secretAccessor` on the three secrets and
`objectViewer` on the dictionary bucket (see `/infra`).

## Status / next
- ✅ **W2** gloss step — cache + Nebius + Claude + passthrough, verified live
- ✅ **W3** dictionary lookup — local + GCS clip stores, synonyms, unmatched
- ✅ **W4** concatenate + slerp blend — per-joint quaternion slerp, resample, rest-hold
- ✅ **API** `POST /api/sign` (+ `/api/ingest`) wiring W2→W3→W4; runs on stub clips, Dockerfile + Cloud Run deploy documented
- ⬜ Deploy to Cloud Run with `CLIP_SOURCE=gcs` once W6 clips land in the `dictionary` bucket
- ⬜ **W1** Vapi assistant → `/api/ingest` end-to-end
