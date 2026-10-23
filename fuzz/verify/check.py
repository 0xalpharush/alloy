#!/usr/bin/env python3
"""Check binary-bound LPS statements and require audited proofs for every target.

Run on the Docker host with uv run --with PyYAML==6.0.3 python. Compilation
uses the pinned reference checker image; no Rocq installation is needed locally.
"""

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

CHECKER = ("ghcr.io/theorem-labs/oss-fuzz-theorems-checker@sha256:"
           "cc9ae43a9f4b0dd59d7c8d30727d36e039bfe72a2a9f9c4a99c68e413037e902")
REFERENCE = "98e995d4daced70a0a4aa2c810854b88720735f1"
BUILDS = {"plain": "Plain", "ubsan": "Ubsan", "asan": "Asan", "asan-ubsan": "AsanUbsan"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=pathlib.Path, required=True)
    parser.add_argument("--work", type=pathlib.Path, required=True)
    parser.add_argument("--reference", type=pathlib.Path, required=True)
    parser.add_argument("--proofs", type=pathlib.Path, required=True)
    parser.add_argument("--statements-only", action="store_true")
    args = parser.parse_args()
    artifacts, work, reference = (p.resolve() for p in
                                  (args.artifacts, args.work, args.reference))
    revision = subprocess.check_output(["git", "-C", str(reference), "rev-parse", "HEAD"],
                                       text=True).strip()
    if revision != REFERENCE:
        raise SystemExit(f"reference must be pinned to {REFERENCE}, got {revision}")
    subprocess.run(["git", "-C", str(reference), "diff", "--exit-code", "HEAD", "--",
                    "theories", "tools/oft", "toolchain/allowed-axioms.txt"], check=True)
    sys.path.insert(0, str(reference))
    # Reuse the reference checker's own assumption audit rather than trusting
    # the exit code or a proof's choice of theorem type.
    from tools.oft.check import allowed_axioms, wrapper_assumptions

    allow = allowed_axioms(str(reference), "toolchain/allowed-axioms.txt")
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit("use an empty checker work directory to exclude stale compiled proofs")
    (work / "core").mkdir()
    (work / "bin").mkdir()
    for name in ("Images.v", "Shapes.v"):
        shutil.copyfile(reference / "theories" / name, work / "core" / name)

    def run(command, cwd="/work", log=None):
        proc = subprocess.run(["docker", "run", "--rm", "--network", "none",
                               "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp",
                               "--ulimit", "stack=-1:-1", "-v", f"{work}:/work",
                               "-w", cwd, CHECKER, *command], check=False, capture_output=True, text=True)
        if log:
            (work / log).write_text(proc.stdout + proc.stderr)
        if proc.returncode:
            raise RuntimeError(f"{command[0]} failed:\n{proc.stdout}\n{proc.stderr}")
        return proc.stdout + proc.stderr

    core_path = ["-Q", "/work/core", "OssFuzzTheorems.Core"]
    for name in ("Images.v", "Shapes.v"):
        run(["rocq", "compile", *core_path, f"/work/core/{name}"], log=f"core/{name}.log")
    sources = json.loads((artifacts / "plain/source-manifest.json").read_text())
    if not sources:
        raise SystemExit("source manifest has no targets")
    if sorted(s["target"] for s in sources) != ["consensus_rlp", "engine_ssz"]:
        raise SystemExit("source manifest must cover both of this PR's targets exactly once")
    for build in BUILDS:
        if json.loads((artifacts / build / "source-manifest.json").read_text()) != sources:
            raise SystemExit(f"{build}: source manifests differ between builds")
    results = []
    for source in sources:
        target = source["target"]
        if not target.replace("_", "").isalnum():
            raise SystemExit(f"invalid Rocq target identifier: {target!r}")
        directory = work / target
        directory.mkdir()
        namespace = f"AlloyProof.{target}"
        qpath = [*core_path, "-Q", f"/work/{target}", namespace]
        hashes = {}
        definitions = []
        for build, module in BUILDS.items():
            binary = artifacts / build / target
            hashes[build] = digest(binary)
            shutil.copyfile(binary, work / "bin" / f"{target}.{build}")
            run(["elf-snapshot", f"/work/bin/{target}.{build}", f"{module}.v", "--prefix", module,
                 "--module-name", "M", "--namespace", namespace], cwd=f"/work/{target}",
                log=f"{target}/{build}-snapshot.log")
            name = build.replace("-", "_")
            definitions.append(f'''Definition {name} : Image := mkImage {module}.M.loaded_segments {module}.M.init_pc {module}.M.phdrs.
Lemma {name}_wf : image_wf {name}. Proof. check_image_wf. Qed.
''')
        (directory / "Images.v").write_text(f'''From LinuxProcessSemantics.LinuxProcessSem Require Import MemImageType.
From OssFuzzTheorems.Core Require Import Images.
From {namespace} Require {" ".join(BUILDS.values())}.
''' + "\n".join(definitions))
        obligations = []
        for build in BUILDS:
            name = build.replace("-", "_")
            obligations.append(f'''Definition {name}_halts : Prop :=
  halts_within_budget Budgets.Standard.lim_source Exits.ok_or_refused Images.{name}.
''')
        (directory / "Statements.v").write_text(f'''(** Binary SHA-256 hashes: {json.dumps(hashes, sort_keys=True)}.
    Under LPS's forced-only environment, for every valid process input and
    launch within each build's 16 GiB memory premise, every execution exits 0 or 2.
    In particular, Rust panic status 79 and all crashes are excluded.
    The reference driver's file-size and input-format rules apply. *)
From OssFuzzTheorems.Core Require Import Shapes.
From {namespace} Require Images.
''' + "\n".join(obligations) + r'''Definition panic_free : Prop :=
  plain_halts /\ ubsan_halts /\ asan_halts /\ asan_ubsan_halts.
''')
        fingerprint = hashlib.sha256((json.dumps(hashes, sort_keys=True) + digest(directory / "Statements.v")
                                      + digest(directory / "Images.v")
                                      + digest(work / "core/Images.v")
                                      + digest(work / "core/Shapes.v") + REFERENCE).encode()).hexdigest()
        for file in (*[f"{module}.v" for module in BUILDS.values()], "Images.v", "Statements.v"):
            run(["rocq", "compile", *qpath, file], cwd=f"/work/{target}",
                log=f"{target}/{file}.log")
        result = {**source, "binary_sha256": hashes,
                  "statement_fingerprint": fingerprint, "status": "unproved"}
        proof_dir = args.proofs.resolve() / target
        if not args.statements_only and (proof_dir / "Proof.v").is_file():
            files = sorted(proof_dir.glob("*.v"))
            for file in files:
                if file.name in {*(f"{m}.v" for m in BUILDS.values()), "Images.v", "Statements.v", "Wrapper.v"}:
                    raise SystemExit(f"proof attempts to replace a checker-owned file: {file.name}")
                shutil.copyfile(file, directory / file.name)
            own = {file.name for file in files}
            ordered = run(["rocq", "dep", "-sort", *qpath, *sorted(own)],
                          cwd=f"/work/{target}").split()
            for file in ordered:
                if pathlib.Path(file).name in own:
                    run(["rocq", "compile", *qpath, file], cwd=f"/work/{target}",
                        log=f"{target}/{pathlib.Path(file).name}.log")
            (directory / "Wrapper.v").write_text(f'''Require {namespace}.Statements.
Require {namespace}.Proof.
Definition certified : {namespace}.Statements.panic_free :=
  {namespace}.Proof.panic_free_holds.
Set Printing Fully Qualified.
Print Assumptions certified.
''')
            assumptions = run(["rocq", "compile", *qpath, "Wrapper.v"],
                              cwd=f"/work/{target}", log=f"{target}/wrapper.log")
            axioms = wrapper_assumptions(assumptions)
            if axioms - allow:
                raise SystemExit(f"unapproved proof assumptions: {sorted(axioms - allow)}")
            result.update(status="proved", axioms=sorted(axioms))
        results.append(result)
        print(f"{target}: {result['status']} (four binary-bound obligations)", flush=True)
    (work / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    if not args.statements_only and any(r["status"] != "proved" for r in results):
        raise SystemExit("PANIC FREEDOM UNPROVED: complete Proof.v files are required for every target")


if __name__ == "__main__":
    main()
