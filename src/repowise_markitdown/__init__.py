"""Register in-memory PDF extraction without loading MarkItDown eagerly."""


def register() -> None:
    try:
        from repowise.core.ingestion.document_extractors import document_extractors
    except ImportError as exc:
        raise RuntimeError(
            "repowise-markitdown requires Repowise's document-extractor seam. "
            "Install a compatible Repowise version as described in the README."
        ) from exc

    from .extractor import PdfDocumentExtractor

    document_extractors.register("markitdown", PdfDocumentExtractor())
