from __future__ import annotations

import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from repowise_markitdown import register
from repowise_markitdown.extractor import PdfDocumentExtractor

from .conftest import make_pdf


def test_registration_claims_only_pdf_without_loading_markitdown():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from repowise_markitdown import register; register(); "
            "from repowise.core.ingestion.document_extractors import document_extractors; "
            "claims = dict(document_extractors.all())['markitdown'].extensions; "
            "assert claims == frozenset({'.pdf'}); "
            "assert 'markitdown' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(
        ep.name == "markitdown" and ep.load() is register
        for ep in entry_points(group="repowise.plugins")
    )


def test_extract_uses_supplied_bytes_not_live_path(tmp_path):
    path = tmp_path / "guide.PDF"
    path.write_bytes(b"not the supplied PDF")
    before = set(tmp_path.rglob("*"))
    extractor = PdfDocumentExtractor()
    assert "Snapshot text" in extractor.extract(path, make_pdf("Snapshot text"))
    assert "Snapshot text" in extractor.extract(tmp_path / "missing.pdf", make_pdf("Snapshot text"))
    assert path.read_bytes() == b"not the supplied PDF"
    assert set(tmp_path.rglob("*")) == before


def test_invalid_pdf_fails():
    from markitdown import FileConversionException

    with pytest.raises(FileConversionException):
        PdfDocumentExtractor().extract(Path("guide.pdf"), b"invalid PDF")


def test_empty_pdf_reports_ocr_requirement():
    with pytest.raises(ValueError, match="No text extracted.*OCR"):
        PdfDocumentExtractor().extract(Path("guide.pdf"), make_pdf(""))


def test_converter_disables_other_formats_and_plugins(monkeypatch):
    from unittest.mock import Mock

    import markitdown
    from markitdown.converters import PdfConverter

    converter = Mock()
    converter.convert_stream.return_value.text_content = "# Extracted\n"
    factory = Mock(return_value=converter)
    monkeypatch.setattr(markitdown, "MarkItDown", factory)
    assert PdfDocumentExtractor().extract(Path("guide.pdf"), b"snapshot") == "# Extracted\n"
    factory.assert_called_once_with(enable_builtins=False, enable_plugins=False)
    assert isinstance(converter.register_converter.call_args.args[0], PdfConverter)
    assert converter.convert_stream.call_args.args[0].getvalue() == b"snapshot"


def test_cache_version_tracks_plugin_and_converter(monkeypatch):
    from repowise_markitdown import extractor

    versions = {"repowise-markitdown": "2.0.0", "markitdown": "0.1.9"}
    monkeypatch.setattr(extractor, "version", versions.__getitem__)
    first = PdfDocumentExtractor().version
    versions["markitdown"] = "0.1.10"
    second = PdfDocumentExtractor().version
    versions["repowise-markitdown"] = "2.0.1"
    assert first != second != PdfDocumentExtractor().version


def test_old_host_reports_missing_seam(monkeypatch):
    monkeypatch.setitem(sys.modules, "repowise.core.ingestion.document_extractors", None)
    with pytest.raises(RuntimeError, match="requires Repowise's document-extractor seam"):
        register()
