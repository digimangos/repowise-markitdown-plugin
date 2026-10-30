from __future__ import annotations

import asyncio
import os
import sqlite3
import subprocess
import sys

import pytest

from .conftest import make_pdf


def _ingest(repository):
    from repowise.core.pipeline.phases.ingestion import _run_ingestion

    return asyncio.run(
        _run_ingestion(
            repository,
            exclude_patterns=None,
            skip_tests=False,
            skip_infra=False,
            progress=None,
        )
    )


def test_real_spawn_extraction_and_host_cache(repository, monkeypatch):
    from repowise.core.ingestion import document_extractors as seam

    pdf = repository / "guide.PDF"
    pdf.write_bytes(make_pdf("Original document"))
    parsed, _infos, _structure, sources, *_ = _ingest(repository)
    document = next(item for item in parsed if item.file_info.path == "guide.PDF")
    assert b"Original document" in sources["guide.PDF"]
    assert document.file_info.extractor_name == "markitdown"
    assert document.file_info.extracted_source == sources["guide.PDF"]
    original_hash = document.content_hash

    def fail_if_extracted(requests, **kwargs):
        assert not requests, "Unchanged PDF must use Repowise's parse cache"
        return []

    with monkeypatch.context() as patch:
        patch.setattr(seam, "extract_documents_bounded", fail_if_extracted)
        cached, *_ = _ingest(repository)
    assert next(item for item in cached if item.file_info.path == "guide.PDF").content_hash == (
        original_hash
    )
    pdf.write_bytes(make_pdf("Updated document"))
    changed, _infos, _structure, sources, *_ = _ingest(repository)
    assert b"Updated document" in sources["guide.PDF"]
    assert next(item for item in changed if item.file_info.path == "guide.PDF").content_hash != (
        original_hash
    )
    assert not list(repository.rglob("*.md"))
    assert not (repository / ".repowise-pdfs").exists()


def test_plain_init_update_and_deletion_use_original_pdf_paths(repository, tmp_path):
    home = tmp_path.parent / f"{tmp_path.name}-home"
    home.mkdir()
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "REPOWISE_SKIP_EDITOR_SETUP": "1",
    }
    if "PYTHONPATH" in os.environ:
        environment["PYTHONPATH"] = os.environ["PYTHONPATH"]
    root_pdf = repository / "guide.pdf"
    root_pdf.write_bytes(make_pdf("Root PDF"))
    nested_pdf = repository / "documents/guide.PDF"
    nested_pdf.parent.mkdir()
    nested_pdf.write_bytes(make_pdf("Nested PDF"))

    def commit():
        subprocess.run(
            ["git", "-C", str(repository), "add", "-A", "--", "guide.pdf", "documents"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "-c",
                "user.name=Plugin Test",
                "-c",
                "user.email=plugin@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "PDF change",
            ],
            env=environment,
            check=True,
        )

    def run(*arguments):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from repowise.cli.main import cli; cli()",
                *arguments,
            ],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def stored_paths():
        with sqlite3.connect(repository / ".repowise/wiki.db") as db:
            return {row[0] for row in db.execute("SELECT file_path FROM graph_nodes")}

    commit()
    run(
        "init",
        str(repository),
        "--no-prose",
        "--yes",
        "--no-editor-setup",
        "--no-claude-md",
        "--no-hook",
    )
    assert {"guide.pdf", "documents/guide.PDF"} <= stored_paths()
    assert root_pdf.read_bytes() == make_pdf("Root PDF")
    root_pdf.write_bytes(make_pdf("Root PDF changed"))
    commit()
    run("update", str(repository), "--index-only")
    assert {"guide.pdf", "documents/guide.PDF"} <= stored_paths()
    nested_pdf.unlink()
    commit()
    run("update", str(repository), "--index-only")
    assert "documents/guide.PDF" not in stored_paths()
    assert "guide.pdf" in stored_paths()
    assert not (repository / ".repowise-pdfs").exists()
    assert not list(repository.rglob("*.pdf.md"))


@pytest.mark.parametrize("data", [b"not a PDF", make_pdf("")])
def test_extraction_failure_names_plugin_and_source(repository, data):
    from repowise.core.ingestion.document_extractors import DocumentExtractionError

    (repository / "broken.pdf").write_bytes(data)
    with pytest.raises(DocumentExtractionError, match=r"markitdown.*broken\.pdf"):
        _ingest(repository)
    assert not list(repository.rglob("*.md"))
