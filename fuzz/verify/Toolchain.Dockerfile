# Retain the reference musl/ASan toolchain and rebuild Rust's standard library
# with a compiler that meets Alloy's MSRV. The dated distributions are checked
# against the Rust distribution's published SHA-256 files.
FROM ghcr.io/theorem-labs/oss-fuzz-theorems-toolchain-rust@sha256:ad8a4572d32dcb70ea3c4ac90e0c4d9c4ecd5cc61721792b0b456b748469e48f

RUN apk add --no-cache uv xz wget tar
RUN set -eu; mkdir /tmp/rust-modern; cd /tmp/rust-modern; \
    for component in rustc cargo rust-src; do \
      if [ "$component" = rust-src ]; then archive=rust-src-nightly; \
      else archive=$component-nightly-x86_64-unknown-linux-musl; fi; \
      wget -q https://static.rust-lang.org/dist/2026-04-01/$archive.tar.xz; \
      wget -q https://static.rust-lang.org/dist/2026-04-01/$archive.tar.xz.sha256; \
      sha256sum -c $archive.tar.xz.sha256; \
      tar -xf $archive.tar.xz; \
      sh $archive/install.sh --prefix=/opt/rust-modern --disable-ldconfig; \
    done; \
    rm -rf /tmp/rust-modern
RUN set -eu; mkdir /tmp/rust-host-std; cd /tmp/rust-host-std; \
    archive=rust-std-nightly-x86_64-unknown-linux-musl; \
    wget -q https://static.rust-lang.org/dist/2026-04-01/$archive.tar.xz; \
    wget -q https://static.rust-lang.org/dist/2026-04-01/$archive.tar.xz.sha256; \
    sha256sum -c $archive.tar.xz.sha256; tar -xf $archive.tar.xz; \
    sh $archive/install.sh --prefix=/opt/rust-modern --disable-ldconfig; \
    rm -rf /tmp/rust-host-std

ENV PATH=/opt/rust-modern/bin:$PATH
ENV CARGO_HOME=/opt/cargo-modern
ENV OFT_RUST_STOCK_LIBRARY=/opt/rust-modern/lib/rustlib/src/rust/library
ENV OFT_RUST_SEALED_LIBRARY=/opt/oft-rust-modern/library-sealed
ENV OFT_RUST_STD_VENDOR=/opt/oft-rust-modern/std-vendor
ENV OFT_RUST_TARGET=/opt/oft-rust-modern/targets/rv64g-oft-linux-musl.json

RUN mkdir -p /opt/oft-rust-modern/targets; \
    cp /opt/oft-rust/seal-std.sh /opt/oft-rust-modern/seal-std.sh; \
    sed -i 's@std/src/sys/pal/unix/thread.rs@std/src/sys/thread/unix.rs@g' /opt/oft-rust-modern/seal-std.sh; \
    /opt/oft-rust-modern/seal-std.sh "$OFT_RUST_STOCK_LIBRARY" "$OFT_RUST_SEALED_LIBRARY" /opt/oft-rust-modern
RUN cargo vendor --locked --versioned-dirs \
      --manifest-path "$OFT_RUST_STOCK_LIBRARY/Cargo.toml" "$OFT_RUST_STD_VENDOR"
RUN rustc -Z unstable-options --target riscv64gc-unknown-linux-musl --print target-spec-json \
      > /tmp/target.json
RUN uv run --no-project python -c 'import json, os; p=json.load(open("/tmp/target.json")); p["features"]="+m,+a,+f,+d,+zicsr,+zifencei"; p["supported-sanitizers"]=["address"]; json.dump(p,open(os.environ["OFT_RUST_TARGET"],"w"),indent=2)'
# The environment also reaches Cargo's nested standard-library build, unlike
# supplying the custom-target opt-in only on the outer Cargo invocation.
ENV CARGO_UNSTABLE_JSON_TARGET_SPEC=true
RUN rustc -vV; sha256sum "$OFT_RUST_TARGET" /opt/oft-rust-modern/seal-std.diff
