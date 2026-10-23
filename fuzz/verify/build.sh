#!/bin/sh -e
# Build both original cargo-fuzz entry points with the published OSS Verify driver.
[ -z "${BASH_VERSION:-}" ] || exec sh -e "$0"
. /usr/local/lib/oss-verify/release-target.sh

for target in consensus_rlp engine_ssz; do
(
    ov_target_begin "$target"
    CARGO_FUZZ_DIR=fuzz
    FUZZ_BIN=$target
    CARGO_DEBUG_ASSERTIONS=1
    CARGO_FEATURES=""
    CARGO_NO_DEFAULT_FEATURES=0
    CARGO_PROFILE_ENV="CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS=true"
    OFT_RUST_QUIET_STDIO=0
    . /usr/local/lib/oss-verify/rust/recipes.sh
    build_lib() {
        oft_build_cargo_shim
        oft_seal_getenv
    }
    LIB_ARCHIVE="lib/liboft.a"
    ov_target_build "$target"
)
done
cp /work/source-manifest.json "$OUT/source-manifest.json"
