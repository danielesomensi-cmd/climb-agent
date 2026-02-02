#!/usr/bin/env python3
"""Apply a patch and push changes in a Colab-style fastlane workflow."""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
from typing import Iterable


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check)


def run_shell(command: str) -> None:
    run(["bash", "-lc", command])


def remote_origin_exists() -> bool:
    result = subprocess.run(["git", "remote", "get-url", "origin"], check=False)
    return result.returncode == 0


def get_remote_origin_url() -> str | None:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def detect_format_patch(patch_path: str) -> bool:
    with open(patch_path, "r", encoding="utf-8", errors="replace") as handle:
        for _ in range(20):
            line = handle.readline()
            if not line:
                break
            if line.startswith("From ") or "Subject: [PATCH" in line:
                return True
    return False


def ensure_origin(repo_url: str) -> None:
    if remote_origin_exists():
        return
    run(["git", "remote", "add", "origin", repo_url])


def checkout_base(base: str, remote: str) -> None:
    run(["git", "checkout", base])
    run(["git", "pull", "--ff-only", remote, base])


def checkout_branch(branch: str) -> None:
    result = subprocess.run(["git", "rev-parse", "--verify", branch], check=False)
    if result.returncode == 0:
        run(["git", "checkout", branch])
    else:
        run(["git", "checkout", "-b", branch])


def apply_patch(patch_path: str, commit_msg: str | None) -> None:
    if detect_format_patch(patch_path):
        try:
            run(["git", "am", patch_path])
        except subprocess.CalledProcessError:
            run(["git", "am", "--abort"], check=False)
            run(["git", "am", "--3way", patch_path])
        return

    if not commit_msg:
        raise SystemExit("--commit_msg is required when patch is not format-patch")

    run(["git", "apply", patch_path])
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", commit_msg])


def run_commands(commands: Iterable[str]) -> None:
    for command in commands:
        run_shell(command)


def push_with_pat(remote: str, repo_url: str, branch: str) -> None:
    original_url = get_remote_origin_url()
    token = getpass.getpass("GitHub PAT: ")
    if not token:
        raise SystemExit("Missing PAT; aborting push.")

    if repo_url.startswith("https://"):
        token_url = repo_url.replace("https://", f"https://{token}@", 1)
    else:
        token_url = f"https://{token}@github.com/{repo_url}"

    try:
        run(["git", "remote", "set-url", remote, token_url])
        run(["git", "push", "--dry-run", remote, branch])
        run(["git", "push", remote, branch])
    finally:
        if original_url:
            run(["git", "remote", "set-url", remote, original_url])
        else:
            run(["git", "remote", "remove", remote])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Colab fastlane apply+push helper")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--patch", required=True)
    parser.add_argument("--base", default="main")
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--repo_url",
        default="https://github.com/danielesomensi-cmd/climb-agent.git",
    )
    parser.add_argument("--commit_msg")
    parser.add_argument("--run", action="append", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    patch_path = os.path.abspath(args.patch)
    if not os.path.exists(patch_path):
        raise SystemExit(f"Patch not found: {patch_path}")

    ensure_origin(args.repo_url)
    run(["git", "fetch", args.remote, "--prune"])
    checkout_base(args.base, args.remote)
    checkout_branch(args.branch)
    apply_patch(patch_path, args.commit_msg)
    run_commands(args.run)
    push_with_pat(args.remote, args.repo_url, args.branch)


if __name__ == "__main__":
    main()
