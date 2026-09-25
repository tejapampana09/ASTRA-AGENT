from __future__ import annotations

import ast
import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.observability.logging import logger


class ChunkType(str, Enum):
    FILE_HEADER = "file_header"
    CLASS = "class"
    FUNCTION = "function"
    API_ROUTE = "api_route"
    DB_MODEL = "db_model"
    TEST = "test"
    CONFIG = "config"
    DOCUMENTATION = "documentation"


@dataclass
class IndexedCodeChunk:
    chunk_id: str
    repo_id: str
    file_path: str
    symbol: str
    chunk_type: ChunkType
    language: str
    content: str
    embedding: Optional[List[float]] = None
    commit_sha: Optional[str] = None
    start_line: int = 1
    end_line: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "repo_id": self.repo_id,
            "file_path": self.file_path,
            "symbol": self.symbol,
            "chunk_type": self.chunk_type.value,
            "language": self.language,
            "content": self.content,
            "embedding": self.embedding,
            "commit_sha": self.commit_sha,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "metadata": self.metadata,
        }


class SemanticCodeChunker:
    """
    Parses source code into semantic, structural chunks rather than arbitrary text splits.
    Classifies chunks by architectural role (API route, DB model, function, test, config, docs).
    """

    ROUTE_DECORATORS = {"get", "post", "put", "delete", "patch", "api_route", "route"}
    DB_MODEL_BASES = {"base", "declarativebase", "basemodel", "model", "document"}
    CONFIG_NAMES = {"pyproject.toml", "requirements.txt", "setup.py", "package.json", ".env.example", "Dockerfile"}

    @classmethod
    def get_git_file_meta(cls, file_path: Path, repo_root: Path) -> Dict[str, Any]:
        """Extracts commit sha, author, and date for a file if in a git repo."""
        meta = {"commit_sha": None, "commit_msg": None}
        try:
            res = subprocess.run(
                ["git", "log", "-1", "--format=%H|%an|%s", "--", str(file_path)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split("|", 2)
                if len(parts) >= 1:
                    meta["commit_sha"] = parts[0]
                if len(parts) >= 3:
                    meta["commit_msg"] = parts[2]
        except Exception:
            pass
        return meta

    @classmethod
    def make_chunk_id(cls, repo_id: str, file_path: str, symbol: str, start_line: int) -> str:
        raw = f"{repo_id}:{file_path}:{symbol}:{start_line}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def chunk_python_file(cls, repo_id: str, file_path: Path, repo_root: Path) -> List[IndexedCodeChunk]:
        rel_path = file_path.relative_to(repo_root).as_posix()
        chunks: List[IndexedCodeChunk] = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
        except Exception as e:
            logger.debug(f"Failed to read file {file_path}: {e}")
            return []

        git_meta = cls.get_git_file_meta(file_path, repo_root)
        commit_sha = git_meta.get("commit_sha")

        is_test_file = "test_" in file_path.name or file_path.name.endswith("_test.py") or "tests" in rel_path.split("/")

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            # If syntax error, create a fallback full file chunk
            chunk_id = cls.make_chunk_id(repo_id, rel_path, "syntax_error", 1)
            return [
                IndexedCodeChunk(
                    chunk_id=chunk_id,
                    repo_id=repo_id,
                    file_path=rel_path,
                    symbol=file_path.name,
                    chunk_type=ChunkType.FILE_HEADER,
                    language="python",
                    content=content[:4000],
                    commit_sha=commit_sha,
                    start_line=1,
                    end_line=len(lines),
                    metadata={"error": "SyntaxError parsing AST"}
                )
            ]

        # Extract file header / imports / module docstring
        module_doc = ast.get_docstring(tree)
        file_imports: List[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    file_imports.append(a.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for a in node.names:
                    file_imports.append(f"{mod}.{a.name}")

        header_lines = []
        for i, line in enumerate(lines[:30]):
            if line.strip().startswith(("import ", "from ", "#", '"""', "'''")):
                header_lines.append(line)
            elif not line.strip():
                header_lines.append(line)
            else:
                break

        if header_lines:
            header_content = "\n".join(header_lines)
            chunk_id = cls.make_chunk_id(repo_id, rel_path, "header", 1)
            chunks.append(
                IndexedCodeChunk(
                    chunk_id=chunk_id,
                    repo_id=repo_id,
                    file_path=rel_path,
                    symbol="file_header",
                    chunk_type=ChunkType.FILE_HEADER,
                    language="python",
                    content=header_content,
                    commit_sha=commit_sha,
                    start_line=1,
                    end_line=len(header_lines),
                    metadata={
                        "docstring": module_doc,
                        "imports": file_imports,
                    }
                )
            )

        # Walk AST top-level and classes
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_chunks = cls._chunk_class_node(
                    repo_id=repo_id,
                    rel_path=rel_path,
                    node=node,
                    lines=lines,
                    commit_sha=commit_sha,
                    is_test_file=is_test_file,
                    file_imports=file_imports
                )
                chunks.extend(cls_chunks)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_chunk = cls._chunk_function_node(
                    repo_id=repo_id,
                    rel_path=rel_path,
                    node=node,
                    lines=lines,
                    commit_sha=commit_sha,
                    is_test_file=is_test_file,
                    file_imports=file_imports
                )
                chunks.append(fn_chunk)

        return chunks

    @classmethod
    def _chunk_class_node(
        cls,
        repo_id: str,
        rel_path: str,
        node: ast.ClassDef,
        lines: List[str],
        commit_sha: Optional[str],
        is_test_file: bool,
        file_imports: List[str]
    ) -> List[IndexedCodeChunk]:
        chunks: List[IndexedCodeChunk] = []
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line + len(node.body))
        content = "\n".join(lines[start_line - 1:end_line])

        bases = [cls._get_name(b).lower() for b in node.bases]
        is_db_model = any(b in cls.DB_MODEL_BASES for b in bases) or "model" in node.name.lower() or "record" in node.name.lower()
        is_test_class = is_test_file or node.name.startswith("Test")

        if is_db_model:
            chunk_type = ChunkType.DB_MODEL
        elif is_test_class:
            chunk_type = ChunkType.TEST
        else:
            chunk_type = ChunkType.CLASS

        docstring = ast.get_docstring(node)
        chunk_id = cls.make_chunk_id(repo_id, rel_path, node.name, start_line)

        # Extract columns / field attributes if model
        attributes: List[str] = []
        methods: List[str] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)

        chunks.append(
            IndexedCodeChunk(
                chunk_id=chunk_id,
                repo_id=repo_id,
                file_path=rel_path,
                symbol=node.name,
                chunk_type=chunk_type,
                language="python",
                content=content,
                commit_sha=commit_sha,
                start_line=start_line,
                end_line=end_line,
                metadata={
                    "bases": [cls._get_name(b) for b in node.bases],
                    "docstring": docstring,
                    "methods": methods,
                    "attributes": attributes,
                    "imports": file_imports,
                }
            )
        )

        return chunks

    @classmethod
    def _chunk_function_node(
        cls,
        repo_id: str,
        rel_path: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: List[str],
        commit_sha: Optional[str],
        is_test_file: bool,
        file_imports: List[str]
    ) -> IndexedCodeChunk:
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line + len(node.body))
        content = "\n".join(lines[start_line - 1:end_line])

        # Inspect decorators to identify API routes
        is_route = False
        http_method = None
        http_path = None
        decorator_names = []

        for d in node.decorator_list:
            d_name = cls._get_name(d).lower()
            decorator_names.append(d_name)
            
            # Check specific HTTP verb attributes e.g., app.get, router.post
            for verb in ["post", "get", "put", "delete", "patch", "head", "options"]:
                if d_name.endswith(f".{verb}") or d_name == verb:
                    is_route = True
                    http_method = verb.upper()
                    if isinstance(d, ast.Call) and d.args:
                        if isinstance(d.args[0], ast.Constant) and isinstance(d.args[0].value, str):
                            http_path = d.args[0].value
                    break

            if not is_route and any(r in d_name for r in ["api_route", "route"]):
                is_route = True
                http_method = "API"
                if isinstance(d, ast.Call) and d.args:
                    if isinstance(d.args[0], ast.Constant) and isinstance(d.args[0].value, str):
                        http_path = d.args[0].value

        is_test = is_test_file or node.name.startswith("test_")

        if is_route:
            chunk_type = ChunkType.API_ROUTE
            symbol = f"{http_method or 'API'} {http_path or node.name}"
        elif is_test:
            chunk_type = ChunkType.TEST
            symbol = node.name
        else:
            chunk_type = ChunkType.FUNCTION
            symbol = node.name

        docstring = ast.get_docstring(node)
        params = [arg.arg for arg in node.args.args]

        # Extract internal function calls / dependencies within body
        called_symbols = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                c_name = cls._get_name(sub.func)
                if c_name:
                    called_symbols.append(c_name)

        chunk_id = cls.make_chunk_id(repo_id, rel_path, symbol, start_line)

        return IndexedCodeChunk(
            chunk_id=chunk_id,
            repo_id=repo_id,
            file_path=rel_path,
            symbol=symbol,
            chunk_type=chunk_type,
            language="python",
            content=content,
            commit_sha=commit_sha,
            start_line=start_line,
            end_line=end_line,
            metadata={
                "docstring": docstring,
                "parameters": params,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "decorators": decorator_names,
                "http_method": http_method,
                "http_path": http_path,
                "calls": list(set(called_symbols)),
                "imports": file_imports,
            }
        )

    @classmethod
    def chunk_config_file(cls, repo_id: str, file_path: Path, repo_root: Path) -> List[IndexedCodeChunk]:
        rel_path = file_path.relative_to(repo_root).as_posix()
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        git_meta = cls.get_git_file_meta(file_path, repo_root)
        chunk_id = cls.make_chunk_id(repo_id, rel_path, "config", 1)

        return [
            IndexedCodeChunk(
                chunk_id=chunk_id,
                repo_id=repo_id,
                file_path=rel_path,
                symbol=file_path.name,
                chunk_type=ChunkType.CONFIG,
                language=file_path.suffix.lstrip(".") or "config",
                content=content[:5000],
                commit_sha=git_meta.get("commit_sha"),
                start_line=1,
                end_line=len(content.splitlines()),
                metadata={"filename": file_path.name}
            )
        ]

    @classmethod
    def chunk_documentation(cls, repo_id: str, file_path: Path, repo_root: Path) -> List[IndexedCodeChunk]:
        rel_path = file_path.relative_to(repo_root).as_posix()
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        git_meta = cls.get_git_file_meta(file_path, repo_root)
        chunk_id = cls.make_chunk_id(repo_id, rel_path, "docs", 1)

        return [
            IndexedCodeChunk(
                chunk_id=chunk_id,
                repo_id=repo_id,
                file_path=rel_path,
                symbol=file_path.name,
                chunk_type=ChunkType.DOCUMENTATION,
                language="markdown",
                content=content[:6000],
                commit_sha=git_meta.get("commit_sha"),
                start_line=1,
                end_line=len(content.splitlines()),
                metadata={"title": file_path.stem}
            )
        ]

    @classmethod
    def _get_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = cls._get_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        elif isinstance(node, ast.Call):
            return cls._get_name(node.func)
        return ""


class RepositorySemanticIndexer:
    """
    Scans, parses, and indexes an entire repository into semantic code chunks.
    Covers Python AST, API routes, DB models, tests, configuration, docs, and git history.
    """

    EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", "dist", "build"}
    CONFIG_NAMES = {"pyproject.toml", "requirements.txt", "setup.py", "package.json", ".env.example", "Dockerfile"}

    @classmethod
    def index_repository(cls, repo_path: Path, repo_id: str = "default_repo") -> List[IndexedCodeChunk]:
        chunks: List[IndexedCodeChunk] = []

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDE_DIRS]

            for file in files:
                f_path = Path(root) / file

                if file.endswith(".py"):
                    file_chunks = SemanticCodeChunker.chunk_python_file(repo_id, f_path, repo_path)
                    chunks.extend(file_chunks)

                elif file in cls.CONFIG_NAMES or file.endswith((".toml", ".ini", ".cfg", ".yaml", ".yml")):
                    conf_chunks = SemanticCodeChunker.chunk_config_file(repo_id, f_path, repo_path)
                    chunks.extend(conf_chunks)

                elif file.endswith((".md", ".rst", ".txt")) and ("README" in file.upper() or "DOC" in file.upper() or "ARCHITECTURE" in file.upper()):
                    doc_chunks = SemanticCodeChunker.chunk_documentation(repo_id, f_path, repo_path)
                    chunks.extend(doc_chunks)

        logger.info(f"Indexed repository {repo_id}: {len(chunks)} semantic chunks generated.")
        return chunks
