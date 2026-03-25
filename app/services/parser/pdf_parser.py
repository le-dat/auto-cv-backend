import fitz


class PDFParser:
    media_types = ["application/pdf"]
    extensions = ["pdf"]

    async def extract_text(self, raw: bytes) -> str:
        doc = fitz.open(stream=raw, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
