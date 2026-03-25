from app.services.parser.pdf_parser import PDFParser
from app.services.parser.docx_parser import DocxParser
from app.services.parser.text_parser import TextParser
from app.core.exceptions import ParseError

# Add new format: instantiate + append here. Zero other changes needed.
_registry: list = [PDFParser(), DocxParser(), TextParser()]

_by_mime = {m: p for p in _registry for m in p.media_types}
_by_ext = {e: p for p in _registry for e in p.extensions}


class ParserService:
    async def parse_file(
        self, raw: bytes, filename: str, content_type: str | None = None
    ) -> str:
        """Resolve parser from MIME type first, then file extension."""
        parser = _by_mime.get(content_type or "") or _by_ext.get(
            filename.rsplit(".", 1)[-1].lower()
        )
        if not parser:
            raise ParseError(
                f"Unsupported input: content_type={content_type}, file={filename}"
            )
        return await parser.extract_text(raw)

    async def parse_text(self, text: str) -> str:
        """Direct text input — no parsing needed."""
        return text.strip()
