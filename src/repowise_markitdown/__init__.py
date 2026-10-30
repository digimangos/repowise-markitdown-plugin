"""Register in-memory PDF extraction without loading MarkItDown eagerly."""


def register() -> None:
    try:
        from repowise.core.ingestion.document_extractors import document_extractors
    except ImportError as exc:
        raise RuntimeError(
            "repowise-markitdown 2 requires Repowise's document-extractor seam. "
            "Install the compatible host described in the README; published "
            "Repowise 0.59.0 does not provide this API."
        ) from exc

    from .extractor import PdfDocumentExtractor

    document_extractors.register("markitdown", PdfDocumentExtractor())
