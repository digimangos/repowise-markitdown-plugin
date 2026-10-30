"""Publish once, resuming drafts without replacing any existing release asset."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from validate_release import validate_distributions, validate_version


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, stdout=subprocess.PIPE, text=True
    ).stdout.strip()


def publish(tag: str, commit: str, dist: Path) -> None:
    name, version = validate_version(Path("pyproject.toml"), tag)
    artifacts = validate_distributions(dist, name, version)
    remote_commit = gh("api", f"repos/{{owner}}/{{repo}}/commits/{tag}", "--jq", ".sha")
    if remote_commit != commit:
        raise ValueError("remote tag no longer points to the workflow commit")

    def find_release() -> dict | None:
        # Listing includes drafts, which the by-tag endpoint need not return.
        pages = json.loads(
            gh(
                "api",
                "--paginate",
                "--slurp",
                "repos/{owner}/{repo}/releases?per_page=100",
            )
        )
        releases = [release for page in pages for release in page if release["tag_name"] == tag]
        if len(releases) > 1:
            raise ValueError("multiple releases for this tag; manual review required")
        return releases[0] if releases else None

    release = find_release()
    if release is None:
        gh(
            "release",
            "create",
            tag,
            "--verify-tag",
            "--target",
            commit,
            "--draft",
            "--generate-notes",
            "--title",
            tag,
        )
        release = find_release()
        if release is None:
            raise ValueError("created draft could not be found")

    if release.get("target_commitish") != commit:
        raise ValueError("release commit provenance is missing or differs from the workflow commit")

    expected = {path.name: path for path in artifacts}
    existing = {asset["name"] for asset in release["assets"]}
    if existing - expected.keys():
        raise ValueError("release contains unexpected assets; manual review required")
    if not release["draft"] and existing != expected.keys():
        raise ValueError("published release is incomplete; refusing to modify it")

    with tempfile.TemporaryDirectory() as directory:
        for filename in sorted(existing):
            gh("release", "download", tag, "--pattern", filename, "--dir", directory)
            if (Path(directory) / filename).read_bytes() != expected[filename].read_bytes():
                raise ValueError(f"existing asset differs: {filename}; refusing to overwrite")
    for filename in sorted(expected.keys() - existing):
        gh("release", "upload", tag, str(expected[filename]))
    if release["draft"]:
        gh("release", "edit", tag, "--draft=false")
    print(f"Release {tag} verified and published")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    publish(args.tag, args.commit, args.dist)


if __name__ == "__main__":
    main()
