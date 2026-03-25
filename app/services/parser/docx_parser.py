import docx
import io


class DocxParser:
    media_types = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    extensions = ["docx"]

    async def extract_text(self, raw: bytes) -> str:
        doc = docx.Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
