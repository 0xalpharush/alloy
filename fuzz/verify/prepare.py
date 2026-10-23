#!/usr/bin/env python3
"""Prepare unchanged fuzz targets for OSS Verify in a separate build tree."""

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tomllib


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--work", type=pathlib.Path, required=True)
    parser.add_argument("--adapter", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    work = args.work.resolve()
    adapter = args.adapter.resolve()
    if work.is_relative_to(source):
        raise SystemExit("the build tree must be outside the source tree")
    manifest = tomllib.loads((source / "fuzz/Cargo.toml").read_text())
    targets = manifest["bin"]
    lock = (source / "fuzz/Cargo.lock").read_text()
    root_name = manifest["package"]["name"]
    runtime = tomllib.loads((adapter / "oft-rust-rt/Cargo.toml").read_text())["package"]
    # Change only the root package identity and add the dependency-free adapter.
    # cargo vendor --locked below must accept this graph without resolving updates.
    package = re.compile(r'(?ms)^\[\[package\]\]\nname = "' + re.escape(root_name)
                         + r'"\n.*?(?=^\[\[package\]\]|\Z)')
    matches = list(package.finditer(lock))
    if len(matches) != 1:
        raise SystemExit("expected exactly one fuzz root in Cargo.lock")
    block = matches[0].group().replace(f'name = "{root_name}"', 'name = "oft-rust-shim"', 1)
    block = block.replace('dependencies = [\n', 'dependencies = [\n "oft-rust-rt",\n', 1)
    lock = package.sub(lambda _: block, lock)
    lock += f'\n[[package]]\nname = "{runtime["name"]}"\nversion = "{runtime["version"]}"\n'
    records = []
    for target in targets:
        name = target["name"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise SystemExit(f"unsupported target name: {name!r}")
        root = work / "ext" / name
        if root.exists():
            raise SystemExit(f"refusing to overwrite {root}")
        tree = root / "src"
        shutil.copytree(source, tree, ignore=shutil.ignore_patterns(
            ".git", "target", "corpus", "artifacts", "__pycache__"))
        (tree / ".oft-scratch-copy").touch()
        # The reviewed host build script generates corpus files. It contributes
        # no runtime code to either target. Keep its bytes for provenance while
        # suppressing Cargo's automatic build-script discovery in this copy.
        build_script = tree / "fuzz/build.rs"
        build_hash = sha256(build_script)
        build_script.rename(tree / "fuzz/seed-build.rs.not-compiled")
        harness = pathlib.Path("fuzz") / target["path"]
        if sha256(tree / harness) != sha256(source / harness):
            raise SystemExit(f"harness changed while copying: {name}")
        out = work / "targets" / name
        out.mkdir(parents=True)
        (out / "Cargo.lock").write_text(lock)
        shim = root / "shim"
        subprocess.run([sys.executable, str(adapter / "gen-shim.py"), "--src", str(tree),
                        "--fuzz-dir", "fuzz", "--bin", name, "--out", str(shim),
                        "--rt", str(adapter / "oft-rust-rt")], check=True)
        (shim / "Cargo.lock").write_text(lock)
        vendor = root / "vendor"
        result = subprocess.run(["cargo", "vendor", "--locked", "--versioned-dirs",
                                 "--manifest-path", str(shim / "Cargo.toml"), str(vendor)],
                                check=False, capture_output=True, text=True)
        (out / "vendor.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise SystemExit(result.stderr)
        if (shim / "Cargo.lock").read_bytes() != (out / "Cargo.lock").read_bytes():
            raise SystemExit("vendoring changed the dependency lock")
        # There are no git dependencies in this pinned fuzz package. Refuse
        # rather than dropping a future git source's replacement configuration.
        if '[source."git+' in result.stdout:
            raise SystemExit("git dependency source mapping needs explicit support")
        (vendor / ".oft-git-sources.toml").write_text("")
        (vendor / ".oft-vendor-lock-sha256").write_text(sha256(out / "Cargo.lock") + "\n")
        records.append({"target": name, "harness": str(harness),
                        "harness_sha256": sha256(source / harness),
                        "shared_types_sha256": sha256(source / "fuzz/types.rs"),
                        "seed_build_script_sha256": build_hash,
                        "source_lock_sha256": sha256(source / "fuzz/Cargo.lock"),
                        "adapter_lock_sha256": sha256(out / "Cargo.lock")})
    (work / "source-manifest.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()
