"""Extract supplied PDF bytes without creating repository-side Markdown copies."""

from __future__ import annotations

from importlib.metadata import version
from io import BytesIO
from pathlib import Path


class PdfDocumentExtractor:
    extensions = frozenset({".pdf"})

    def __init__(self) -> None:
        self.version = (
            f"repowise-markitdown/{version('repowise-markitdown')};"
            f"markitdown/{version('markitdown')}"
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
        if not isinstance(text, str) or not text.strip():
            raise ValueError("No text extracted; scanned PDFs may require a separate OCR step")
        return text.rstrip() + "\n"
