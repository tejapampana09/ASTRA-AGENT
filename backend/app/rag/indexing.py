from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.observability.logging import logger


@dataclass
class CodeChunk:
    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: str = ""


class CodeChunker:
    """Splits source files into semantic chunks by functions and classes."""

    @classmethod
    def chunk_file(cls, file_path: Path, rel_path: str, max_chunk_lines: int = 50) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            # Window chunking
            start = 0
            while start < len(lines):
                end = min(start + max_chunk_lines, len(lines))
                chunk_text = "\n".join(lines[start:end])
                chunks.append(
                    CodeChunk(
                        file_path=rel_path,
                        start_line=start + 1,
                        end_line=end,
                        content=chunk_text
                    )
                )
                start += max_chunk_lines
        except Exception as e:
            logger.debug(f"Error chunking file {file_path}: {e}")

        return chunks
