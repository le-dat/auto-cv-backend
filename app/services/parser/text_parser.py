class TextParser:
    media_types = ["text/plain", "text/markdown"]
    extensions = ["txt", "text", "md"]

    async def extract_text(self, raw: bytes) -> str:
        return raw.decode("utf-8", errors="replace").strip()
