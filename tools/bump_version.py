"""
tools/bump_version.py - Semantic Versioning auto-bump tool for OmniGrab.

Usage (local machine):
    python tools/bump_version.py patch     # 4.0.2 -> 4.0.3
    python tools/bump_version.py minor     # 4.0.2 -> 4.1.0
    python tools/bump_version.py major     # 4.0.2 -> 5.0.0
    python tools/bump_version.py none      # Print current version, no change

Called by CI/CD:
    python tools/bump_version.py patch --ci --commit --tag

Flags:
    --ci        Silent mode (no interactive prompts)
    --commit    Auto git add + commit + create local tag
    --tag       Push tag to origin after commit
    --dry-run   Print what would change, but don't write anything
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT_DIR / "core" / "version.py"
ISS_FILE = ROOT_DIR / "setup.iss"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_current_version() -> str:
    content = VERSION_FILE.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([\d]+\.[\d]+\.[\d]+)"', content)
    if not m:
        print("[ERROR] Cannot parse APP_VERSION from core/version.py", file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def _bump(version: str, kind: str) -> str:
    parts = version.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if kind == "major":
        return f"{major + 1}.0.0"
    elif kind == "minor":
        return f"{major}.{minor + 1}.0"
    elif kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif kind == "none":
        return version
    else:
        print(f"[ERROR] Unknown bump kind: '{kind}'. Use: major / minor / patch / none", file=sys.stderr)
        sys.exit(1)


def _write_version_py(new_version: str, dry_run: bool) -> None:
    content = VERSION_FILE.read_text(encoding="utf-8")
    new_content = re.sub(
        r'(APP_VERSION\s*=\s*")[^"]+(")',
        rf'\g<1>{new_version}\g<2>',
        content,
    )
    if dry_run:
        print(f"  [dry-run] Would update {VERSION_FILE} -> APP_VERSION = \"{new_version}\"")
        return
    VERSION_FILE.write_text(new_content, encoding="utf-8")
    print(f"  [OK] {VERSION_FILE.relative_to(ROOT_DIR)} -> APP_VERSION = \"{new_version}\"")


def _write_iss(new_version: str, dry_run: bool) -> None:
    content = ISS_FILE.read_text(encoding="utf-8")
    new_content = re.sub(
        r'(#define\s+MyAppVersion\s+")[^"]+(")',
        rf'\g<1>{new_version}\g<2>',
        content,
    )
    if dry_run:
        print(f"  [dry-run] Would update {ISS_FILE} -> MyAppVersion = \"{new_version}\"")
        return
    ISS_FILE.write_text(new_content, encoding="utf-8")
    print(f"  [OK] {ISS_FILE.relative_to(ROOT_DIR)} -> MyAppVersion = \"{new_version}\"")


def _git_commit_and_tag(new_version: str, push_tag: bool, dry_run: bool) -> None:
    tag = f"v{new_version}"
    files = [str(VERSION_FILE), str(ISS_FILE)]
    cmds: list[list[str]] = [
        ["git", "add"] + files,
        ["git", "commit", "-m", f"chore(release): bump version to {tag} [skip ci]"],
        ["git", "tag", "-f", tag],
    ]
    if push_tag:
        cmds.append(["git", "push", "origin", tag, "--force"])

    for cmd in cmds:
        if dry_run:
            print(f"  [dry-run] Would run: {' '.join(cmd)}")
            continue
        result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] Command failed: {' '.join(cmd)}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)
        else:
            print(f"  [git] {' '.join(cmd[:3])}..." )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    bump_kind = "patch"
    ci_mode = "--ci" in args
    do_commit = "--commit" in args
    push_tag = "--tag" in args
    dry_run = "--dry-run" in args

    # First positional argument is the bump kind
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        bump_kind = positional[0].lower()

    current = _read_current_version()
    new_version = _bump(current, bump_kind)

    if bump_kind == "none":
        print(f"Current version: {current} (no change)")
        return

    sep = "-" * 50
    print(sep)
    print(f"  OmniGrab Version Bump: {current} -> {new_version} ({bump_kind.upper()})")
    print(sep)

    if not ci_mode and not dry_run:
        answer = input(f"Confirm bump {current} -> {new_version}? [Y/n]: ").strip().lower()
        if answer not in ("", "y", "yes"):
            print("Aborted.")
            sys.exit(0)

    _write_version_py(new_version, dry_run)
    _write_iss(new_version, dry_run)

    if do_commit:
        _git_commit_and_tag(new_version, push_tag, dry_run)

    print(f"\n  Version bumped to {new_version} successfully!")
    if not do_commit:
        print("  (Run with --commit to auto git-commit and tag)")

    # Output for CI env file (GitHub Actions)
    github_output = Path(str(__import__("os").environ.get("GITHUB_OUTPUT", "")))
    if github_output.exists() or str(github_output) != "":
        try:
            with open(str(github_output), "a", encoding="utf-8") as f:
                f.write(f"new_version={new_version}\n")
        except Exception:
            pass

    print(f"new_version={new_version}")


if __name__ == "__main__":
    main()
