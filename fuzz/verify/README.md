# Binary-level verification of Alloy's fuzz targets

**Status: universal panic freedom is unproved for both targets.** This directory
adapts the two cargo-fuzz targets to the OSS Verify build and Rocq/LPS checker.
It does not replace missing proofs with fuzzing results or admitted theorems.

On a Linux x86-64 host with Docker, git, uv, and qemu-riscv64 (or
qemu-riscv64-static):

```sh
bash fuzz/verify/run.sh /tmp/alloy-verification --statements-only
```

This builds static RV64G plain, Rust UB-check, ASan, and combined binaries;
generates the original seed corpora and replays them under QEMU; imports each
binary into LPS; and compiles its well-formedness certificate and theorem
statement in the pinned Rocq checker. `--statements-only` reports unproved
statements and does not certify panic freedom. Use a fresh work directory for
each checker run to avoid stale compiled proofs.

The build keeps the original harnesses and dependencies, including all runtime
assertions and expectations. `prepare.py` copies the source to a build tree and
renames its corpus-generating `fuzz/build.rs` there: the published static-library
adapter rejects fuzz package build scripts. The original script still generates
the replay corpora in a separate native host build. Only the adapter package is
added to the dependency lock; vendoring must accept it with `--locked`.

The published Rust toolchain predates Alloy's MSRV. `Toolchain.Dockerfile` layers
the dated Rust compiler and matching rust-src onto the pinned musl/ASan image,
reapplies that image's standard-library seals, and rebuilds the standard library
with the same instrumentation as the target. The seals select nonblocking
entropy and make available_parallelism return one. The optional quiet-stdio seal
is not enabled. The exact seal diff, compiler version, build image IDs, source
hashes, binary hashes and checker outputs are retained in the work directory.

## Required proof

For each target, `check.py` generates a statement about its exact ELF bytes:

```coq
Definition plain_halts : Prop :=
  halts_within_budget Budgets.Standard.lim_source Exits.ok_or_refused Images.plain.
(* The same obligation for each of the three instrumented builds. *)
Definition panic_free : Prop :=
  plain_halts /\ ubsan_halts /\ asan_halts /\ asan_ubsan_halts.
```

Under LPS's valid-input and valid-launch definitions, its forced-only environment
and each build's 16 GiB memory-budget premise, every execution must exit with status 0 or
2. The reference driver's input-file format and file-size limit apply. This
excludes Rust panic status 79, signals, faults, unmodelled steps and divergence.
It is a statement about these compiled binaries and runtime seals, not arbitrary
native builds or the entire Alloy library.

The Rust adapter translates a panic into status 79. Agreement between two
builds could therefore permit both to panic; sanitizer agreement alone does not
establish this panic-freedom claim.

Put complete Rocq sources in `proofs/consensus_rlp/` and `proofs/engine_ssz/`.
Each `Proof.v` must export `panic_free_holds` at the generated statement's type.
For example, the consensus proof imports
`From AlloyProof.consensus_rlp Require Import Statements.`

Run without `--statements-only` to require both proofs:

```sh
bash fuzz/verify/run.sh /tmp/alloy-verification-with-proofs
```

The checker compiles an independently generated wrapper at the exact statement
type, then audits `Print Assumptions` using the pinned reference checker's parser
and allowed-axiom list. It fails if either proof is absent, has the wrong type,
or introduces an unapproved assumption. No `Proof.v` files are supplied yet.

To check new proofs against existing binaries without rebuilding, use a fresh
checker output directory:

```sh
uv run --with PyYAML==6.0.3 python fuzz/verify/check.py \
  --artifacts /tmp/alloy-verification/out \
  --work /tmp/alloy-proof-check \
  --reference /tmp/alloy-verification/oss-verify-proofs \
  --proofs fuzz/verify/proofs
```

`bash fuzz/verify/test-checker.sh /tmp/alloy-verification/oss-verify-proofs`
runs the reference checker's four positive and five negative proof controls.

References:

- [OSS Verify build contract](https://github.com/theorem-labs/oss-verify/blob/dfe93eb82e3f99037e9ad837821f87f3d7029e60/docs/build-contract.md)
- [Proof method and limitations](https://github.com/theorem-labs/oss-verify-proofs/blob/98e995d4daced70a0a4aa2c810854b88720735f1/README.md)
- [Proof acceptance rules](https://github.com/theorem-labs/oss-verify-proofs/blob/98e995d4daced70a0a4aa2c810854b88720735f1/docs/proving.md)
