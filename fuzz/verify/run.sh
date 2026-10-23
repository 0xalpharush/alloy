#!/usr/bin/env bash
# Build, replay seeds, and check statements/proofs for both fuzz targets.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 || ( $# -eq 2 && $2 != --statements-only ) ]]; then
    echo "Usage: $0 WORK_DIRECTORY [--statements-only]" >&2
    exit 2
fi
source_root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
mkdir -p "$1"
work=$(cd "$1" && pwd -P)
case "$work/" in "$source_root/"*) echo 'Work directory must be outside the repository' >&2; exit 2 ;; esac
mode=${2:-}
for tool in docker git uv; do command -v "$tool" >/dev/null; done
qemu=$(command -v qemu-riscv64 || command -v qemu-riscv64-static)
jobs=${VERIFY_JOBS:-8}
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { echo 'VERIFY_JOBS must be positive' >&2; exit 2; }

clone_pinned() {
    local name=$1 revision=$2
    if [[ ! -d "$work/$name" ]]; then
        git clone --filter=blob:none --no-checkout "https://github.com/theorem-labs/$name" "$work/$name"
        if [[ $name == oss-verify-proofs ]]; then
            git -C "$work/$name" sparse-checkout set theories toolchain tools/oft tests
        fi
    fi
    git -C "$work/$name" diff --exit-code
    git -C "$work/$name" checkout --detach "$revision"
}
clone_pinned oss-verify dfe93eb82e3f99037e9ad837821f87f3d7029e60
clone_pinned oss-verify-proofs 98e995d4daced70a0a4aa2c810854b88720735f1
mkdir -p "$work/logs" "$work/out" "$work/seeds"
git -C "$source_root" rev-parse HEAD > "$work/source-commit.txt"
git -C "$source_root" diff HEAD -- crates fuzz > "$work/source.diff"

echo 'Building compatible Rust toolchain'
docker build -t alloy-verify-toolchain -f "$source_root/fuzz/verify/Toolchain.Dockerfile" \
    "$source_root/fuzz/verify" > "$work/logs/toolchain.log" 2>&1
docker run --rm --network none alloy-verify-toolchain rustc -vV > "$work/compiler.txt"
docker run --rm --network none alloy-verify-toolchain cat /opt/oft-rust-modern/seal-std.diff \
    > "$work/standard-library-seals.diff"
docker build -t alloy-verify-builder --build-arg TOOLCHAIN=alloy-verify-toolchain \
    "$work/oss-verify/infra/base-builder" > "$work/logs/builder.log" 2>&1
docker build -t alloy-verify-project -f "$source_root/fuzz/verify/Dockerfile" \
    "$source_root" > "$work/logs/project.log" 2>&1
docker image inspect alloy-verify-toolchain alloy-verify-builder alloy-verify-project > "$work/images.json"

echo 'Generating seed corpora with the original host build script'
docker run --rm --network none -v "$work/seeds:/src/alloy/fuzz/corpus" alloy-verify-project \
    cargo check --manifest-path /src/alloy/fuzz/Cargo.toml --locked --offline \
    > "$work/logs/seeds.log" 2>&1

: > "$work/binaries.sha256"
for flavor in plain ubsan asan asan-ubsan; do
    case $flavor in
        plain) sanitizer=none ;;
        ubsan) sanitizer=undefined ;;
        asan) sanitizer=address ;;
        asan-ubsan) sanitizer=address-undefined ;;
    esac
    echo "Building $flavor binaries"
    mkdir -p "$work/out/$flavor"
    docker run --rm --network none -e "SANITIZER=$sanitizer" -e "OFT_MAKE_JOBS=$jobs" \
        -e "OV_OWNER=$(id -u):$(id -g)" \
        -v "$work/out/$flavor:/out" alloy-verify-project compile > "$work/logs/$flavor.log" 2>&1
    for target in consensus_rlp engine_ssz; do
        binary="$work/out/$flavor/$target"
        sha256sum "$binary" >> "$work/binaries.sha256"
        printf '\0\0\0\0\0\0' > "$work/input.bin"
        "$qemu" "$binary" "$work/input.bin" > "$work/logs/$flavor-$target-empty.log" 2>&1
        count=0
        for seed in "$work/seeds/$target"/*; do
            [[ -f $seed ]] || continue
            { printf '\0\0\0\0\0\0'; cat "$seed"; } > "$work/input.bin"
            "$qemu" "$binary" "$work/input.bin" >> "$work/logs/$flavor-$target-seeds.log" 2>&1
            count=$((count + 1))
        done
        [[ $count -gt 0 ]] || { echo "No seeds generated for $target" >&2; exit 1; }
        echo "$flavor/$target: empty payload and $count seed inputs returned successfully"
    done
done

echo 'Compiling binary-bound Rocq statements and checking supplied proofs'
check_work=$(mktemp -d "$work/check-XXXXXX")
echo "Checker output: $check_work"
uv run --with PyYAML==6.0.3 python "$source_root/fuzz/verify/check.py" \
    --artifacts "$work/out" --work "$check_work" \
    --reference "$work/oss-verify-proofs" --proofs "$source_root/fuzz/verify/proofs" ${mode:+"$mode"}
