#!/usr/bin/env bash
# W0 — GCP bootstrap for the Voice-to-ASL Signing Avatar POC.
# Idempotent: re-running skips resources that already exist.
# Usage: ./infra/setup.sh
set -euo pipefail

PROJECT=${PROJECT:-buildday-499318}
REGION=${REGION:-us-central1}
SA_NAME=signing-runtime
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

echo ">> Project: $PROJECT  Region: $REGION"

echo ">> Enabling required APIs"
gcloud services enable \
  run.googleapis.com storage.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com \
  --project="$PROJECT"

echo ">> Buckets: dictionary (clips), smplx-model (model assets), frontend (static site)"
for B in dictionary smplx-model frontend; do
  gcloud storage buckets create "gs://${PROJECT}-${B}" \
    --project="$PROJECT" --location="$REGION" --uniform-bucket-level-access \
    || echo "   exists: ${PROJECT}-${B}"
done

echo ">> Artifact Registry (Docker) for Cloud Run images"
gcloud artifacts repositories create signing-avatar \
  --project="$PROJECT" --repository-format=docker --location="$REGION" \
  --description="Container images for voice-to-ASL signing avatar" \
  || echo "   exists: signing-avatar"

echo ">> Cloud Run runtime service account"
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT" --display-name="Cloud Run runtime (gloss/lookup/blend)" \
  || echo "   exists: $SA"

echo ">> Secrets (values added later with: gcloud secrets versions add <NAME> --data-file=-)"
# ANTHROPIC_API_KEY pre-existed in the project; only the two below are created here.
for S in VAPI_API_KEY NEBIUS_API_KEY; do
  gcloud secrets create "$S" --project="$PROJECT" --replication-policy=automatic \
    || echo "   exists: $S"
done

echo ">> Grant runtime SA: secretAccessor on the three runtime secrets"
for S in VAPI_API_KEY NEBIUS_API_KEY ANTHROPIC_API_KEY; do
  gcloud secrets add-iam-policy-binding "$S" --project="$PROJECT" \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor" --condition=None >/dev/null
done

echo ">> Grant runtime SA: objectViewer on dictionary + smplx-model buckets"
for B in dictionary smplx-model; do
  gcloud storage buckets add-iam-policy-binding "gs://${PROJECT}-${B}" \
    --member="serviceAccount:${SA}" --role="roles/storage.objectViewer" >/dev/null
done

echo ">> Done. Resources:"
echo "   buckets: gs://${PROJECT}-dictionary  gs://${PROJECT}-smplx-model  gs://${PROJECT}-frontend"
echo "   AR repo: ${REGION}-docker.pkg.dev/${PROJECT}/signing-avatar"
echo "   SA:      ${SA}"
echo "   secrets: VAPI_API_KEY  NEBIUS_API_KEY  ANTHROPIC_API_KEY"
