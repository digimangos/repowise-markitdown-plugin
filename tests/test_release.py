from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_script("validate_release")
publisher = load_script("publish_release")


@pytest.fixture
def distribution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text(
        '[project]\nname = "repowise-markitdown"\nversion = "1.2.3"\n'
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / ".gitignore").write_text("*\n")
    metadata = b"Name: repowise-markitdown\nVersion: 1.2.3\n"
    with zipfile.ZipFile(dist / "repowise_markitdown-1.2.3-py3-none-any.whl", "w") as wheel:
        wheel.writestr("repowise_markitdown-1.2.3.dist-info/METADATA", metadata)
    with tarfile.open(dist / "repowise_markitdown-1.2.3.tar.gz", "w:gz") as sdist:
        member = tarfile.TarInfo("repowise_markitdown-1.2.3/PKG-INFO")
        member.size = len(metadata)
        sdist.addfile(member, io.BytesIO(metadata))
    return dist


@pytest.mark.parametrize("version", ["0.0.0", "0.1.0", "1.2.3", "10.20.30"])
def test_valid_versions(tmp_path: Path, version: str) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(f'[project]\nname = "example"\nversion = "{version}"\n')
    assert validator.validate_version(project, f"v{version}") == ("example", version)


@pytest.mark.parametrize(
    "version", ["01.2.3", "1.02.3", "1.2.03", "1.2", "1.2.3rc1", "1.2.3+build"]
)
def test_invalid_versions(tmp_path: Path, version: str) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(f'[project]\nname = "example"\nversion = "{version}"\n')
    with pytest.raises(ValueError, match="project.version"):
        validator.validate_version(project)


@pytest.mark.parametrize("tag", ["1.2.3", "v1.2.4", "v01.2.3", "v1.2.3-rc1", "v1.2.3+build"])
def test_tag_mismatch(distribution: Path, tag: str) -> None:
    with pytest.raises(ValueError, match="tag must be"):
        validator.validate_version(Path("pyproject.toml"), tag)


def test_distribution_checksums(distribution: Path) -> None:
    validator.validate_distributions(distribution, "repowise-markitdown", "1.2.3")
    checksum = distribution / "SHA256SUMS"
    for line in checksum.read_text().splitlines():
        digest, filename = line.split("  ")
        assert digest == hashlib.sha256((distribution / filename).read_bytes()).hexdigest()
    previous = checksum.read_bytes()
    validator.validate_distributions(distribution, "repowise-markitdown", "1.2.3")
    assert checksum.read_bytes() == previous


def test_stale_distribution(distribution: Path) -> None:
    (distribution / "stale.whl").touch()
    with pytest.raises(ValueError, match="expected"):
        validator.validate_distributions(distribution, "repowise-markitdown", "1.2.3")


@pytest.mark.parametrize(
    "filename",
    ["repowise_markitdown-1.2.3-py3-none-any.whl", "repowise_markitdown-1.2.3.tar.gz"],
)
def test_missing_distribution(distribution: Path, filename: str) -> None:
    (distribution / filename).unlink()
    with pytest.raises(ValueError, match="expected"):
        validator.validate_distributions(distribution, "repowise-markitdown", "1.2.3")


def test_checksum_mismatch(distribution: Path) -> None:
    (distribution / "SHA256SUMS").write_text("incorrect checksums\n")
    with pytest.raises(ValueError, match="SHA256SUMS"):
        validator.validate_distributions(distribution, "repowise-markitdown", "1.2.3")


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_metadata_mismatch(distribution: Path, kind: str) -> None:
    metadata = b"Name: repowise-markitdown\nVersion: 9.9.9\n"
    if kind == "wheel":
        with zipfile.ZipFile(
            distribution / "repowise_markitdown-1.2.3-py3-none-any.whl", "w"
        ) as archive:
            archive.writestr("repowise_markitdown-1.2.3.dist-info/METADATA", metadata)
    else:
        with tarfile.open(distribution / "repowise_markitdown-1.2.3.tar.gz", "w:gz") as archive:
            member = tarfile.TarInfo("repowise_markitdown-1.2.3/PKG-INFO")
            member.size = len(metadata)
            archive.addfile(member, io.BytesIO(metadata))
    with pytest.raises(ValueError, match="metadata"):
        validator.validate_distributions(distribution, "repowise-markitdown", "1.2.3")


@pytest.mark.parametrize(
    ("state", "error"),
    [
        ("new", None),
        ("draft", None),
        ("published", None),
        ("different", "existing asset differs"),
        ("incomplete", "published release is incomplete"),
        ("unexpected", "unexpected assets"),
        ("moved", "remote tag"),
        ("forbidden", "non-zero exit status"),
    ],
)
def test_safe_publication(
    distribution: Path, monkeypatch: pytest.MonkeyPatch, state: str, error: str | None
) -> None:
    artifacts = validator.validate_distributions(distribution, "repowise-markitdown", "1.2.3")
    filenames = [path.name for path in artifacts]
    existing = filenames if state in {"published", "different"} else filenames[:1]
    if state == "unexpected":
        existing = ["unexpected.txt"]
    calls = []
    created = False

    def fake_gh(*args: str) -> str:
        nonlocal created
        calls.append(args)
        if args[0] == "api" and args[1].endswith("/commits/v1.2.3"):
            return "other" if state == "moved" else "commit"
        if args[0] == "api":
            if state == "forbidden":
                raise subprocess.CalledProcessError(1, args, stderr="HTTP 403")
            if state == "new" and not created:
                return "[]"
            return json.dumps(
                [
                    [
                        {
                            "tag_name": "v1.2.3",
                            "target_commitish": "commit",
                            "draft": state in {"new", "draft"},
                            "assets": [
                                {"name": filename} for filename in ([] if created else existing)
                            ],
                        }
                    ]
                ]
            )
        if args[:2] == ("release", "create"):
            assert args[args.index("--target") + 1] == "commit"
            created = True
        if args[:2] == ("release", "download"):
            filename = args[args.index("--pattern") + 1]
            destination = Path(args[args.index("--dir") + 1]) / filename
            destination.write_bytes(
                b"different" if state == "different" else (distribution / filename).read_bytes()
            )
        return ""

    monkeypatch.setattr(publisher, "gh", fake_gh)
    if error:
        with pytest.raises((ValueError, subprocess.CalledProcessError), match=error):
            publisher.publish("v1.2.3", "commit", distribution)
        assert not any(args[:2] in {("release", "upload"), ("release", "edit")} for args in calls)
    else:
        publisher.publish("v1.2.3", "commit", distribution)
        uploads = [args for args in calls if args[:2] == ("release", "upload")]
        assert len(uploads) == {"new": 3, "draft": 2, "published": 0}[state]
        assert ("release", "edit", "v1.2.3", "--draft=false") in calls or state == "published"


@pytest.mark.parametrize("draft", [True, False])
@pytest.mark.parametrize("origin", ["commit-a", "main", None])
def test_rejects_cross_run_or_unverifiable_provenance(
    distribution: Path, monkeypatch: pytest.MonkeyPatch, draft: bool, origin: str | None
) -> None:
    calls = []

    def fake_gh(*args: str) -> str:
        calls.append(args)
        if args[0] == "api" and args[1].endswith("/commits/v1.2.3"):
            # Both the moved tag and the new workflow now point at B, not A.
            return "commit-b"
        if args[0] == "api":
            release = {"tag_name": "v1.2.3", "draft": draft, "assets": []}
            if origin is not None:
                release["target_commitish"] = origin
            return json.dumps([[release]])
        pytest.fail(f"Provenance rejection must precede release operations: {args}")

    monkeypatch.setattr(publisher, "gh", fake_gh)
    with pytest.raises(ValueError, match="release commit provenance"):
        publisher.publish("v1.2.3", "commit-b", distribution)
    assert all(args[0] == "api" for args in calls)
