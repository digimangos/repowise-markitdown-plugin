"""Validate the authoritative package version and built distribution metadata."""

from __future__ import annotations

import argparse
import hashlib
import re
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", re.ASCII)


def validate_version(project: Path, tag: str | None = None) -> tuple[str, str]:
    metadata = tomllib.loads(project.read_text())["project"]
    version = metadata["version"]
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError("project.version must be MAJOR.MINOR.PATCH without leading zeroes")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"tag must be v{version}, got {tag!r}")
    return metadata["name"], version


def validate_distributions(dist: Path, name: str, version: str) -> list[Path]:
    normalised = re.sub(r"[-_.]+", "_", name)
    wheel_name = f"{normalised}-{version}-py3-none-any.whl"
    sdist_name = f"{normalised}-{version}.tar.gz"
    expected = {wheel_name, sdist_name}
    actual = {path.name for path in dist.iterdir() if path.name not in {"SHA256SUMS", ".gitignore"}}
    if actual != expected:
        raise ValueError(f"expected {sorted(expected)}, got {sorted(actual)}")

    with zipfile.ZipFile(dist / wheel_name) as wheel:
        wheel_metadata = wheel.read(f"{normalised}-{version}.dist-info/METADATA")
    with tarfile.open(dist / sdist_name, "r:gz") as sdist:
        member = sdist.extractfile(f"{normalised}-{version}/PKG-INFO")
        if member is None:
            raise ValueError("sdist has no package metadata")
        sdist_metadata = member.read()
    for content in (wheel_metadata, sdist_metadata):
        metadata = BytesParser().parsebytes(content)
        if metadata["Name"] != name or metadata["Version"] != version:
            raise ValueError("distribution metadata does not match pyproject.toml")

    checksums = [
        f"{hashlib.sha256((dist / filename).read_bytes()).hexdigest()}  {filename}\n"
        for filename in sorted(expected)
    ]
    checksum_file = dist / "SHA256SUMS"
    content = "".join(checksums)
    if checksum_file.exists() and checksum_file.read_text(encoding="ascii") != content:
        raise ValueError("SHA256SUMS does not match the distributions")
    checksum_file.write_text(content, encoding="ascii")
    return [dist / filename for filename in sorted(expected | {"SHA256SUMS"})]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    name, version = validate_version(Path("pyproject.toml"), args.tag)
    if args.dist is not None:
        validate_distributions(args.dist, name, version)
    print(f"Validated {name} {version}" + (f" for {args.tag}" if args.tag else ""))


if __name__ == "__main__":
    main()
