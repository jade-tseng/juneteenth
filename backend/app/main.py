"""Cloud Run API: POST /api/sign (and the Vapi /api/ingest webhook).

Wires W2 (gloss) -> W3 (lookup) -> W4 (blend). The dictionary is loaded once at
startup from the configured clip store (stub by default; GCS in prod).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import os

from asl_schemas import SignRequest, SMPLXSequence, VapiTranscriptWebhook
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import TRANSITION_FRAMES, clip_store
from .gloss import GlossService
from .lookup import DictionaryLookup
from .pipeline import SignPipeline, UnmatchedError

log = logging.getLogger("asl.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the dictionary + pipeline once (clip store read is the expensive bit).
    lookup = DictionaryLookup.from_store(clip_store())
    app.state.pipeline = SignPipeline(
        gloss=GlossService(),
        lookup=lookup,
        transition_frames=TRANSITION_FRAMES,
    )
    log.info("pipeline ready: %d lexical, %d letter clips",
             len(lookup._lexical), len(lookup._letters))
    yield


app = FastAPI(title="Voice-to-ASL Signing Avatar", lifespan=lifespan)

# The deployed frontend (static on GCS/CDN) calls this API cross-origin; dev uses
# the Vite proxy (same-origin). CORS_ALLOW_ORIGINS is a comma-separated list;
# defaults to "*" for the POC (tighten to the real frontend origin in prod).
_origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _sign(request: Request, text: str):
    pipeline: SignPipeline = request.app.state.pipeline
    try:
        return pipeline.sign(text)
    except UnmatchedError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": "no signs matched", "unmatched": exc.unmatched},
        )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/sign", response_model=SMPLXSequence)
def sign(body: SignRequest, request: Request):
    """text -> SMPLXSequence (200) | {error, unmatched} (422). §3.5"""
    return _sign(request, body.text)


@app.post("/api/ingest")
def ingest(body: VapiTranscriptWebhook, request: Request):
    """Vapi transcript webhook (§3.4) -> signed sequence (or 422)."""
    return _sign(request, body.transcript)
