"""Test doubles and sample files. Tests never call the real AI module."""

from app.services.ai_gateway import AIIngestError, DocMeta, FakeAIGateway, IngestResult

# Smallest inputs that pass the upload signature check (content isn't parsed by the fake AI).
PDF_BYTES = b"%PDF-1.4\n% sample\n"
DOCX_BYTES = b"PK\x03\x04" + b"\x00" * 64


class FailingAIGateway(FakeAIGateway):
    """Ingest fails with a user-safe AI error (e.g. password-protected PDF)."""

    def __init__(self, message: str = "This PDF is password-protected.") -> None:
        super().__init__(ingest_error=AIIngestError(message))


class CrashingAIGateway(FakeAIGateway):
    """Ingest fails with an unexpected error (e.g. Qdrant down)."""

    def __init__(self) -> None:
        super().__init__(ingest_error=RuntimeError("qdrant connection refused at 10.0.0.5"))


__all__ = [
    "DOCX_BYTES",
    "PDF_BYTES",
    "CrashingAIGateway",
    "DocMeta",
    "FailingAIGateway",
    "FakeAIGateway",
    "IngestResult",
]
