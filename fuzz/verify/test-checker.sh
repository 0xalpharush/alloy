#!/usr/bin/env bash
# Run the reference checker's positive and negative proof controls.
set -euo pipefail
reference=${1:?Usage: test-checker.sh OSS_VERIFY_PROOFS_CHECKOUT}
reference=$(cd "$reference" && pwd -P)
revision=$(git -C "$reference" rev-parse HEAD)
[[ $revision == 98e995d4daced70a0a4aa2c810854b88720735f1 ]] || exit 2
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
    --ulimit stack=-1:-1 -v "$reference:/work" -w /work \
    ghcr.io/theorem-labs/oss-fuzz-theorems-checker@sha256:cc9ae43a9f4b0dd59d7c8d30727d36e039bfe72a2a9f9c4a99c68e413037e902 \
    bash -c 'dune build tests && bash tests/check.sh'
