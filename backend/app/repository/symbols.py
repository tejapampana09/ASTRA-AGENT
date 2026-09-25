from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.logging import logger


@dataclass
class CodeSymbol:
    name: str
    kind: str  # "function", "class", "method", "import"
    file_path: str
    line_number: int
    docstring: Optional[str] = None
    parameters: List[str] = field(default_factory=list)


@dataclass
class FileCodeIntelligence:
    file_path: str
    symbols: List[CodeSymbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


class SymbolExtractor:
    """Extracts structural code symbols from source files."""

    @classmethod
    def extract_from_python_file(cls, file_path: Path, rel_path: str) -> FileCodeIntelligence:
        intel = FileCodeIntelligence(file_path=rel_path)
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    doc = ast.get_docstring(node)
                    intel.symbols.append(
                        CodeSymbol(
                            name=node.name,
                            kind="class",
                            file_path=rel_path,
                            line_number=node.lineno,
                            docstring=doc
                        )
                    )
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    doc = ast.get_docstring(node)
                    params = [arg.arg for arg in node.args.args]
                    intel.symbols.append(
                        CodeSymbol(
                            name=node.name,
                            kind="function",
                            file_path=rel_path,
                            line_number=node.lineno,
                            docstring=doc,
                            parameters=params
                        )
                    )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        intel.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        intel.imports.append(f"{mod}.{alias.name}")

        except Exception as e:
            logger.debug(f"Failed to parse symbols from {file_path}: {e}")

        return intel

    @classmethod
    def index_workspace_symbols(cls, workspace_path: Path) -> List[CodeSymbol]:
        all_symbols: List[CodeSymbol] = []
        for p in workspace_path.rglob("*.py"):
            if not any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in p.parts):
                rel = p.relative_to(workspace_path).as_posix()
                intel = cls.extract_from_python_file(p, rel)
                all_symbols.extend(intel.symbols)
        return all_symbols
