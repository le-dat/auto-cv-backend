from typing import Protocol, runtime_checkable


@runtime_checkable
class ParserStrategy(Protocol):
    media_types: list[str]
    extensions: list[str]

    async def extract_text(self, raw: bytes) -> str:
        ...
