# Infra (W0) — GCP bootstrap

POC infrastructure for the Voice-to-ASL Signing Avatar, provisioned via `gcloud`.
Run `./setup.sh` to (re)create everything; it is idempotent.

## Resources

| Concern | Resource |
|---|---|
| Project | `buildday-499318` (number `255790304452`) |
| Region | `us-central1` |
| Dictionary clips (W6 → W3) | bucket `gs://buildday-499318-dictionary` |
| SMPL-X model assets (W5) | bucket `gs://buildday-499318-smplx-model` |
| Frontend static site (INT) | bucket `gs://buildday-499318-frontend` |
| Container images | Artifact Registry `us-central1-docker.pkg.dev/buildday-499318/signing-avatar` |
| Cloud Run identity | SA `signing-runtime@buildday-499318.iam.gserviceaccount.com` |
| Secrets | `VAPI_API_KEY`, `NEBIUS_API_KEY`, `ANTHROPIC_API_KEY` |

## IAM granted to the runtime SA
- `roles/secretmanager.secretAccessor` on all three secrets
- `roles/storage.objectViewer` on the `dictionary` and `smplx-model` buckets

## Add secret values
Secrets are created empty. Add values when keys are available:
```sh
printf '%s' "$VAPI_KEY"     | gcloud secrets versions add VAPI_API_KEY    --data-file=-
printf '%s' "$NEBIUS_KEY"   | gcloud secrets versions add NEBIUS_API_KEY  --data-file=-
# ANTHROPIC_API_KEY already has a value in the project.
```

## Not done yet (deferred to later tickets)
- **Public read** on `smplx-model` / `frontend` buckets + Cloud CDN — set when the
  frontend is deployed (W5/INT). Browser fetches model assets client-side, so those
  objects need `allUsers:objectViewer` (or a backend proxy / signed URLs).
- **Compute Engine + GPU** APIs/quota for the offline extraction VM (W6).
- **Cloud Run service** deploy + secret wiring (API ticket).
- **CI schema validation** (W0, `/schemas` package) — separate from GCP bootstrap.
