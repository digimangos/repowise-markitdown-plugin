"""Extract supplied PDF bytes without creating repository-side Markdown copies."""

from __future__ import annotations

import os
from importlib.metadata import version
from io import BytesIO
from pathlib import Path


class PdfDocumentExtractor:
    extensions = frozenset({".pdf"})

    def __init__(self) -> None:
        policy = os.environ.get("REPOWISE_MARKITDOWN_FAIL_ON_EMPTY", "false").strip().lower()
        if policy not in {"true", "false", "1", "0"}:
            raise ValueError("REPOWISE_MARKITDOWN_FAIL_ON_EMPTY must be true, false, 1 or 0")
        self.fail_on_empty = policy in {"true", "1"}
        self.version = (
            f"repowise-markitdown/{version('repowise-markitdown')};"
            f"markitdown/{version('markitdown')};"
            f"fail-on-empty/{str(self.fail_on_empty).lower()}"
        )

    def extract(self, path: Path, data: bytes) -> str:
        from markitdown import MarkItDown, StreamInfo
        from markitdown.converters import PdfConverter

        converter = MarkItDown(enable_builtins=False, enable_plugins=False)
        converter.register_converter(PdfConverter())
        text = converter.convert_stream(
            BytesIO(data),
            stream_info=StreamInfo(extension=".pdf", mimetype="application/pdf"),
        ).text_content
        if not isinstance(text, str):
            raise ValueError("PDF converter returned non-text output")
        if not text.strip():
            if self.fail_on_empty:
                raise ValueError("No text extracted; scanned PDFs may require a separate OCR step")
            return (
                "# PDF text unavailable\n\n"
                f"Source file: {path.as_posix()}\n\n"
                "No text could be extracted from this PDF. It may contain scanned pages "
                "or images; try an OCR tool to extract its content.\n"
            )
        return text.rstrip() + "\n"
