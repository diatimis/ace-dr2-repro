#!/usr/bin/env python3
"""
package_github_upload.py

Creates a clean staging folder containing only the files you want to upload to GitHub:
- Selected Cobaya run directories (YAMLs, chain txt segments, covmat/progress/checkpoint, optional paramnames)
- Your ~/.bash_aliases (used to summarize runs)
- ~/paper_plots/generate_fig4_fig5_from_chains.py (figure generator)

NEW (optional): capture an environment fingerprint (Conda, pip, Cobaya, CLASS) into tools/env/.
This helps referees reproduce your plotting + verify constraints from the chains.

Usage examples:
  python3 package_github_upload.py --runs ace_global_fixed_desiDR2 lcdm_baseline_desiDR2 --out ace_repo_staging --force --zip --env-snapshot
  python3 package_github_upload.py --auto-detect-runs --out ace_repo_staging --force --targz --env-snapshot
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


# -----------------------------
# Config: what to include/exclude
# -----------------------------

INCLUDE_PATTERNS = [
    "*.yaml",
    "*.input.yaml",
    "*.updated.yaml",
    "*.paramnames",     # if present
    "*.covmat",
    "*.progress",
    "*.checkpoint",
    "*.txt",            # chain segments (*.1.txt, *.2.txt, etc.)
    "*.A.txt", "*.B.txt"
]

EXCLUDE_PATTERNS = [
    "*.log",
    "*.tmp",
    "*.bak",
    "*.npy",
    "*.npz",
    "*.pkl",
    "*.pickle",
    "*.hdf5",
    "*.h5",
    "*.dat",
    "*.fits",
    "*.pdf",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "__pycache__/*",
    ".ipynb_checkpoints/*",
]

EXPLICIT_FILES = [
    "~/.bash_aliases",
    "~/paper_plots/generate_fig4_fig5_from_chains.py",
]

# If you want your README snippet for fig generation to be auto-added later,
# you can keep this string handy; we just capture env here.
FIG_CMD_SNIPPET = r"""python3 generate_fig4_fig5_from_chains.py \
  --tracker-dir ~/ace_global_fixed_desiDR2 \
  --lcdm-dir ~/lcdm_baseline_desiDR2 \
  --output-dir ~/paper_plots
"""


@dataclass
class CopiedFile:
    src: Path
    dst: Path
    size: int
    sha256: str


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def matches_any(path: Path, patterns: List[str]) -> bool:
    name = path.name
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
    rel = path.as_posix()
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def ensure_empty_dir(path: Path, force: bool) -> None:
    if path.exists():
        if not force:
            raise FileExistsError(f"Output directory already exists: {path}\nUse --force to overwrite.")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> CopiedFile:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    size = dst.stat().st_size
    digest = sha256_file(dst)
    return CopiedFile(src=src, dst=dst, size=size, sha256=digest)


def iter_run_files(run_dir: Path) -> Iterable[Path]:
    for p in run_dir.rglob("*"):
        if p.is_file():
            yield p


def detect_run_dirs(base: Path) -> List[Path]:
    candidates = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        yamls = list(d.glob("*.yaml"))
        txts = list(d.glob("*.txt"))
        has_yaml = len(yamls) > 0
        has_chain = any(
            (".1.txt" in t.name or ".2.txt" in t.name or ".3.txt" in t.name or ".4.txt" in t.name)
            for t in txts
        ) or len(txts) > 0
        if has_yaml and has_chain:
            candidates.append(d)
    return sorted(candidates)


def copy_run_dir(run_dir: Path, staging_root: Path, copied: List[CopiedFile]) -> None:
    dst_run_dir = staging_root / run_dir.name
    dst_run_dir.mkdir(parents=True, exist_ok=True)

    for f in iter_run_files(run_dir):
        if matches_any(f, EXCLUDE_PATTERNS):
            continue
        if matches_any(f, INCLUDE_PATTERNS):
            rel = f.relative_to(run_dir)
            dst = dst_run_dir / rel
            copied.append(copy_file(f, dst))


def write_manifest(staging_root: Path, copied: List[CopiedFile]) -> None:
    manifest = staging_root / "MANIFEST.txt"
    total = sum(c.size for c in copied)
    lines = []
    lines.append(f"Total files: {len(copied)}")
    lines.append(f"Total bytes: {total}")
    lines.append("")
    lines.append("sha256  bytes  path")
    for c in sorted(copied, key=lambda x: x.dst.as_posix()):
        rel = c.dst.relative_to(staging_root).as_posix()
        lines.append(f"{c.sha256}  {c.size}  {rel}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_notes(staging_root: Path, base: Path, runs: List[str], env_snapshot: bool) -> None:
    notes = staging_root / "PACKAGING_NOTES.txt"
    txt = f"""Packaging notes

Base directory:
  {base}

Run directories included:
  {', '.join(runs) if runs else '(auto-detected)'}

Included patterns:
  {INCLUDE_PATTERNS}

Excluded patterns:
  {EXCLUDE_PATTERNS}

Explicit extra files:
  {EXPLICIT_FILES}

Environment snapshot captured:
  {env_snapshot}

Figure command used in the paper (for README):
{FIG_CMD_SNIPPET}
"""
    notes.write_text(txt, encoding="utf-8")


def make_archive(staging_root: Path, zip_: bool, targz: bool) -> Optional[Path]:
    if not zip_ and not targz:
        return None

    parent = staging_root.parent
    base_name = staging_root.name

    if zip_:
        out = parent / f"{base_name}.zip"
        if out.exists():
            out.unlink()
        shutil.make_archive(str(parent / base_name), "zip", root_dir=str(parent), base_dir=base_name)
        return out

    if targz:
        out = parent / f"{base_name}.tar.gz"
        if out.exists():
            out.unlink()
        shutil.make_archive(str(parent / base_name), "gztar", root_dir=str(parent), base_dir=base_name)
        return out

    return None


# -----------------------------
# Environment snapshot (venv + no-classy aware)
# -----------------------------


def bash_in_venv(cmd: str, venv_activate: Optional[str]) -> List[str]:
    """
    Returns a bash -lc command list that optionally sources a venv activate script first.
    """
    if venv_activate:
        act = os.path.expanduser(venv_activate)
        return ["bash", "-lc", f"source '{act}'; {cmd}"]
    return ["bash", "-lc", cmd]


def run_bash_to_file(cmd: str, out_path: Path, venv_activate: Optional[str]) -> None:
    """
    Always writes stdout+stderr to file (never empty silently unless command truly prints nothing).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run(
            bash_in_venv(cmd, venv_activate),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        # Always write something
        out_path.write_text(p.stdout if p.stdout else "(no output)\n", encoding="utf-8")
    except Exception as e:
        out_path.write_text(f"ERROR running command:\n{cmd}\n\n{e}\n", encoding="utf-8")

def _pick_existing_path(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists() and p.is_file():
            return p
    return None


def _extract_packages_path_from_grep(grep_text: str) -> Optional[str]:
    """
    Parse grep output lines like:
      ./run/foo.yaml:123:packages_path: /path/to/cobaya_packages
    Returns the first path found, stripped of quotes.
    """
    for line in grep_text.splitlines():
        if "packages_path" not in line:
            continue
        # Split on 'packages_path' then ':' then take tail
        # Handles: packages_path: /x  OR packages_path : "/x"
        parts = line.split("packages_path", 1)[1]
        if ":" in parts:
            tail = parts.split(":", 1)[1].strip()
            # if quoted, capture inside quotes
            if (tail.startswith("'") and "'" in tail[1:]) or (tail.startswith('"') and '"' in tail[1:]):
                q = tail[0]
                tail = tail[1:].split(q, 1)[0]
            else:
                tail = tail.split()[0] if tail else ""
            if tail:
                return tail
    return None


def _find_class_dir(packages_path: Path) -> Optional[Path]:
    """
    Try to locate a CLASS source directory under a Cobaya 'packages_path'.
    Your setup uses packages_path/code/classy.
    """
    if not packages_path.exists():
        return None

    candidates = [
        packages_path / "code" / "class_public",
        packages_path / "code" / "CLASS",
        packages_path / "code" / "class",
        packages_path / "code" / "classy",   # your tree
        packages_path / "class_public",
        packages_path / "CLASS",
        packages_path / "classy",
    ]

    for c in candidates:
        if c.exists() and c.is_dir():
            # sanity check for CLASS-like structure
            if (c / "main" / "class.c").exists() or (c / "include" / "class.h").exists():
                return c
            return c

    # fallback: find a dir that contains main/class.c anywhere under packages_path
    try:
        for p in packages_path.rglob("main"):
            if p.is_dir() and (p / "class.c").exists():
                return p.parent
    except Exception:
        pass

    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()




def _write_class_fingerprint(class_dir: Path, out_file: Path) -> None:
    """
    Write a deterministic fingerprint of the CLASS source tree even if it's not a git repo.
    """
    candidates = [
        "main/class.c",
        "include/common.h",
        "include/background.h",
        "source/background.c",
        "Makefile",
        "python/setup.py",
        "pyproject.toml",
        "setup.py",
    ]

    lines = []
    lines.append(f"class_dir: {class_dir.as_posix()}")
    lines.append("sha256  bytes  relpath")

    found_any = False
    for rel in candidates:
        p = class_dir / rel
        if p.exists() and p.is_file():
            found_any = True
            lines.append(f"{_sha256(p)}  {p.stat().st_size}  {rel}")

    if not found_any:
        # fallback: hash a file listing so there's still something stable
        file_list = sorted([str(x.relative_to(class_dir)) for x in class_dir.rglob("*") if x.is_file()])
        blob = ("\n".join(file_list) + "\n").encode("utf-8")
        lines.append(f"{hashlib.sha256(blob).hexdigest()}  {len(blob)}  __file_list_fallback__")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def capture_env_snapshot(staging_root: Path, venv_activate: Optional[str]) -> None:
    """
    Writes environment fingerprint files into: tools/env/
    - Works for venv activation (source .../bin/activate)
    - Does not assume python module 'classy' exists
    - Attempts to discover Cobaya packages_path from staged YAMLs and/or config locations
    - Attempts to locate CLASS checkout and git hash (best effort)
    """
    env_dir = staging_root / "tools" / "env"
    env_dir.mkdir(parents=True, exist_ok=True)

    # Basics (venv interpreter)
    run_bash_to_file("python -V", env_dir / "python_version.txt", venv_activate)
    run_bash_to_file("which python", env_dir / "python_path.txt", venv_activate)
    run_bash_to_file("python -c \"import sys; print(sys.executable)\"", env_dir / "python_executable.txt", venv_activate)
    run_bash_to_file("uname -a", env_dir / "uname.txt", venv_activate)
    run_bash_to_file("python -c \"import platform; print(platform.platform())\"", env_dir / "platform.txt", venv_activate)

    # Pip snapshot (venv relevant)
    run_bash_to_file("python -m pip -V", env_dir / "pip_version.txt", venv_activate)
    run_bash_to_file("python -m pip freeze", env_dir / "pip-freeze.txt", venv_activate)
    run_bash_to_file("python -m pip show cobaya 2>/dev/null || true", env_dir / "pip-show-cobaya.txt", venv_activate)

    # Cobaya version + file path + CLI
    run_bash_to_file(
        "python -c \"import cobaya; print('cobaya', cobaya.__version__); print('cobaya_file', cobaya.__file__)\"",
        env_dir / "cobaya_version.txt",
        venv_activate,
    )
    run_bash_to_file(
        "python -c \"import shutil; print('cobaya_cli', shutil.which('cobaya'))\"",
        env_dir / "cobaya_cli.txt",
        venv_activate,
    )

    # CLASSy presence (expected False in your setup)
    run_bash_to_file(
        "python -c \"import importlib.util as u; print('classy_found', u.find_spec('classy') is not None)\"",
        env_dir / "classy_present.txt",
        venv_activate,
    )

    # Cobaya config location checks (may or may not exist)
    run_bash_to_file(
        r"""python -c "from pathlib import Path; \
c=[Path('~/.cobaya/config.yaml').expanduser(), Path('~/.config/cobaya/config.yaml').expanduser()]; \
print('config_candidates:'); \
[print(str(p), 'exists='+str(p.exists())) for p in c]" """,
        env_dir / "cobaya_config_candidates.txt",
        venv_activate,
    )

    # Save the actual Cobaya config path and contents (if present)
    cfg_candidates = [
        Path("~/.cobaya/config.yaml").expanduser(),
        Path("~/.config/cobaya/config.yaml").expanduser(),
    ]
    cfg = None
    for p in cfg_candidates:
        if p.exists() and p.is_file():
            cfg = p
            break

    (env_dir / "cobaya_config_path.txt").write_text(
        f"{cfg.as_posix() if cfg else '(no config.yaml found)'}\n",
        encoding="utf-8",
    )

    if cfg:
        try:
            (env_dir / "cobaya_config_contents.txt").write_text(
                cfg.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8",
            )
        except Exception as e:
            (env_dir / "cobaya_config_contents.txt").write_text(
                f"ERROR reading {cfg}:\n{e}\n",
                encoding="utf-8",
            )
    else:
        (env_dir / "cobaya_config_contents.txt").write_text(
            "(no config.yaml found)\n",
            encoding="utf-8",
        )


    # Environment variable (may be unset)
    run_bash_to_file(
        "echo \"COBAYA_PACKAGES_PATH=${COBAYA_PACKAGES_PATH:-'(not set)'}\"",
        env_dir / "cobaya_packages_path_env.txt",
        venv_activate,
    )

    # Grep staged YAMLs for packages_path (this is the key for your case)
    # This runs in the staging root where YAMLs exist in run folders.
    run_bash_to_file(
        "cd '{}' && grep -R \"packages_path\" -n . 2>/dev/null || true".format(staging_root.as_posix()),
        env_dir / "packages_path_grep.txt",
        venv_activate,
    )

    # Parse grep output to extract a first packages_path and then probe it
    grep_text = (env_dir / "packages_path_grep.txt").read_text(encoding="utf-8", errors="replace")
    extracted = _extract_packages_path_from_grep(grep_text)

    resolved_packages_path: Optional[Path] = None
    if extracted:
        resolved_packages_path = Path(os.path.expanduser(extracted))
        # If relative, interpret relative to HOME (common) then staging_root (fallback)
        if not resolved_packages_path.is_absolute():
            home = Path.home()
            if (home / resolved_packages_path).exists():
                resolved_packages_path = (home / resolved_packages_path).resolve()
            else:
                resolved_packages_path = (staging_root / resolved_packages_path).resolve()
        else:
            resolved_packages_path = resolved_packages_path.resolve()

    # Write resolved packages_path
    (env_dir / "packages_path_resolved.txt").write_text(
        f"{resolved_packages_path.as_posix() if resolved_packages_path else '(not found in YAMLs)'}\n",
        encoding="utf-8",
    )

    # If found, list it and try locate CLASS
    if resolved_packages_path and resolved_packages_path.exists():
        # list top level
        run_bash_to_file(
            "ls -la '{}'".format(resolved_packages_path.as_posix()),
            env_dir / "packages_path_ls.txt",
            venv_activate,
        )

        class_dir = _find_class_dir(resolved_packages_path)

        (env_dir / "class_dir_found.txt").write_text(
            f"{class_dir.as_posix() if (class_dir and class_dir.exists()) else '(CLASS dir not found under packages_path)'}\n",
            encoding="utf-8",
        )

        if class_dir and class_dir.exists():
            # Try git hash, but your CLASS tree may not be a git checkout.
            run_bash_to_file(
                "git -C '{}' rev-parse HEAD 2>/dev/null || echo '(not a git repo)'".format(class_dir.as_posix()),
                env_dir / "class_git_hash.txt",
                venv_activate,
            )
            run_bash_to_file(
                "git -C '{}' status --porcelain 2>/dev/null || true".format(class_dir.as_posix()),
                env_dir / "class_git_status.txt",
                venv_activate,
            )
            run_bash_to_file(
                "ls -la '{}'".format(class_dir.as_posix()),
                env_dir / "class_dir_ls.txt",
                venv_activate,
            )

            # Always write a deterministic source fingerprint (works even without .git)
            _write_class_fingerprint(class_dir, env_dir / "class_fingerprint_sha256.txt")
        else:
            (env_dir / "class_git_hash.txt").write_text(
                "(skipped: CLASS dir not found under packages_path)\n",
                encoding="utf-8",
            )
            (env_dir / "class_fingerprint_sha256.txt").write_text(
                "(skipped: CLASS dir not found under packages_path)\n",
                encoding="utf-8",
            )

    else:
        # Provide a clear message so it isn't "empty"
        (env_dir / "packages_path_ls.txt").write_text(
            "packages_path could not be resolved from staged YAMLs.\n"
            "If you used Cobaya externals, add packages_path: /path/to/cobaya_packages to YAML or share Cobaya config.\n",
            encoding="utf-8",
        )
        (env_dir / "class_dir_found.txt").write_text(
            "CLASS dir not searched because packages_path was not found.\n",
            encoding="utf-8",
        )
        (env_dir / "class_git_hash.txt").write_text(
            "(skipped: packages_path not found)\n",
            encoding="utf-8",
        )
        (env_dir / "class_fingerprint_sha256.txt").write_text(
            "(skipped: packages_path not found)\n",
            encoding="utf-8",
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=".", help="Base directory containing the run folders (default: current dir)")
    ap.add_argument("--out", required=True, help="Output staging directory (created fresh)")
    ap.add_argument("--runs", nargs="*", default=None, help="Run folder names to include (space separated)")
    ap.add_argument("--runs-from-file", default=None, help="Text file with one run folder name per line")
    ap.add_argument("--auto-detect-runs", action="store_true", help="Auto-detect run directories under --base")
    ap.add_argument("--force", action="store_true", help="Overwrite --out if it exists")
    ap.add_argument("--zip", dest="zip_", action="store_true", help="Create a zip archive of the staging dir")
    ap.add_argument("--targz", action="store_true", help="Create a tar.gz archive of the staging dir")
    ap.add_argument("--env-snapshot", action="store_true", help="Capture environment fingerprint into tools/env/")
    ap.add_argument(
        "--venv-activate",
        default=None,
        help="Path to venv activate script, e.g. ~/cobaya_env/bin/activate",
    )


    args = ap.parse_args()

    base = Path(os.path.expanduser(args.base)).resolve()
    out = Path(os.path.expanduser(args.out)).resolve()

    if not base.exists():
        print(f"ERROR: base does not exist: {base}", file=sys.stderr)
        return 2

    # Determine run list
    runs: List[str] = []
    if args.runs_from_file:
        rf = Path(os.path.expanduser(args.runs_from_file)).resolve()
        if not rf.exists():
            print(f"ERROR: runs-from-file not found: {rf}", file=sys.stderr)
            return 2
        runs = [
            ln.strip() for ln in rf.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]

    if args.runs:
        runs = list(args.runs)

    run_dirs: List[Path] = []
    if args.auto_detect_runs:
        run_dirs = detect_run_dirs(base)
        runs = [d.name for d in run_dirs]
    else:
        if not runs:
            print("ERROR: Provide --runs ..., or --runs-from-file, or --auto-detect-runs", file=sys.stderr)
            return 2
        for r in runs:
            d = (base / r).resolve()
            if not d.exists() or not d.is_dir():
                print(f"ERROR: run dir not found: {d}", file=sys.stderr)
                return 2
            run_dirs.append(d)

    ensure_empty_dir(out, force=args.force)

    copied: List[CopiedFile] = []

    # Copy run directories
    for d in run_dirs:
        copy_run_dir(d, out, copied)

    # Copy explicit files
    for p in EXPLICIT_FILES:
        src = Path(os.path.expanduser(p)).resolve()
        if not src.exists() or not src.is_file():
            print(f"WARNING: explicit file missing, skipped: {src}", file=sys.stderr)
            continue

        if src.name == ".bash_aliases":
            dst = out / "tools" / ".bash_aliases"
        else:
            dst = out / "paper_plots" / src.name

        copied.append(copy_file(src, dst))

    # Environment fingerprint
    if args.env_snapshot:
        capture_env_snapshot(out, venv_activate=args.venv_activate)


    # Write manifest + notes
    write_manifest(out, copied)
    write_notes(out, base, runs, env_snapshot=args.env_snapshot)

    # Archive if requested
    archive = make_archive(out, zip_=args.zip_, targz=args.targz)
    if archive:
        print(f"Created archive: {archive}")

    print(f"Staging complete: {out}")
    print(f"Files copied: {len(copied)} (manifest excludes env snapshot files)")
    if args.env_snapshot:
        print(f"Environment snapshot: {out / 'tools' / 'env'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

