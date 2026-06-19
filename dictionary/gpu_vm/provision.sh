#!/usr/bin/env bash
# W6 — provision a build-time GPU VM for SMPL-X extraction (CLAUDE.md §7).
# Build-time only: create it, build the dictionary, then DELETE it (see teardown).
# Idempotent-ish: re-running errors if the instance exists (delete it first).
set -euo pipefail

PROJECT=${PROJECT:-buildday-499318}
ZONE=${ZONE:-us-central1-a}
VM=${VM:-smplx-extract}
# L4 is the cheapest modern inference GPU; T4 fallback shown in comments.
MACHINE=${MACHINE:-g2-standard-8}
GPU=${GPU:-type=nvidia-l4,count=1}
SA=${SA:-signing-runtime@${PROJECT}.iam.gserviceaccount.com}

echo ">> Creating GPU VM ${VM} (${MACHINE}, ${GPU}) in ${ZONE}"
gcloud compute instances create "$VM" \
  --project="$PROJECT" --zone="$ZONE" \
  --machine-type="$MACHINE" \
  --accelerator="$GPU" \
  --maintenance-policy=TERMINATE \
  --provisioning-model=SPOT \
  --image-family=common-cu123-ubuntu-2204-py310 \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=120GB --boot-disk-type=pd-ssd \
  --service-account="$SA" \
  --scopes=cloud-platform \
  --metadata="install-nvidia-driver=True"
  # T4 alternative:
  #   --machine-type=n1-standard-8 --accelerator=type=nvidia-tesla-t4,count=1

cat <<EOF

>> VM up. Next:
   gcloud compute scp --zone=${ZONE} --recurse . ${VM}:~/dictionary
   gcloud compute ssh --zone=${ZONE} ${VM} -- 'cd dictionary && bash gpu_vm/setup.sh'
   gcloud compute ssh --zone=${ZONE} ${VM} -- 'cd dictionary && bash gpu_vm/run_build.sh'

>> When done, TEAR DOWN (this is a serving-cost gotcha — no GPU at runtime):
   gcloud compute instances delete ${VM} --zone=${ZONE} --project=${PROJECT}
EOF
