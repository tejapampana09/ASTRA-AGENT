"""Tool registry and execution primitives for ASTRA software engineering agent."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class ToolExecutor:
    """Executes workspace actions safely within the target repository."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = (workspace_path or Path.cwd()).resolve()

    def _resolve_path(self, rel_or_abs_path: str) -> Path:
        p = Path(rel_or_abs_path)
        if not p.is_absolute():
            p = self.workspace_path / p
        return p.resolve()

    def read_file(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Read text from a file with optional line numbers."""
        target = self._resolve_path(file_path)
        if not target.exists():
            return f"Error: File does not exist at '{file_path}'"
        if target.is_dir():
            return f"Error: '{file_path}' is a directory, not a file."

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total_lines = len(lines)

            if start_line is not None or end_line is not None:
                s = max(1, start_line or 1) - 1
                e = min(total_lines, end_line or total_lines)
                sliced = lines[s:e]
                formatted = [f"{s + idx + 1:4d} | {line}" for idx, line in enumerate(sliced)]
                return f"[Showing lines {s+1} to {e} of {total_lines} in {target.name}]\n" + "\n".join(formatted)

            # Cap large files to avoid blowing up context window
            if len(lines) > 400:
                head = lines[:200]
                tail = lines[-100:]
                out = [f"{i+1:4d} | {l}" for i, l in enumerate(head)]
                out.append(f"\n... [{len(lines) - 300} lines omitted] ...\n")
                out.extend([f"{total_lines - 100 + i + 1:4d} | {l}" for i, l in enumerate(tail)])
                return "\n".join(out)

            return "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines))
        except Exception as exc:
            return f"Error reading file '{file_path}': {exc}"

    def write_file(self, file_path: str, content: str) -> str:
        """Create or overwrite a file with the given content."""
        target = self._resolve_path(file_path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to '{file_path}'."
        except Exception as exc:
            return f"Error writing file '{file_path}': {exc}"

    def edit_file(self, file_path: str, target_snippet: str, replacement_snippet: str) -> str:
        """Replace a specific snippet in an existing file."""
        target = self._resolve_path(file_path)
        if not target.exists():
            return f"Error: File does not exist at '{file_path}'"

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            if target_snippet not in content:
                return (
                    f"Error: Target snippet not found in '{file_path}'. "
                    "Make sure the snippet matches the exact indentation and whitespace."
                )

            count = content.count(target_snippet)
            if count > 1:
                return (
                    f"Warning: Target snippet occurs {count} times in '{file_path}'. "
                    "Please provide a more unique snippet to avoid ambiguous replacement."
                )

            new_content = content.replace(target_snippet, replacement_snippet, 1)
            target.write_text(new_content, encoding="utf-8")
            return f"Successfully updated '{file_path}' (replaced 1 instance)."
        except Exception as exc:
            return f"Error editing file '{file_path}': {exc}"

    def list_dir(self, dir_path: str = ".") -> str:
        """List files and subdirectories."""
        target = self._resolve_path(dir_path)
        if not target.exists():
            return f"Error: Path '{dir_path}' does not exist."
        if not target.is_dir():
            return f"Error: Path '{dir_path}' is not a directory."

        try:
            entries = []
            for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name.startswith(".") and item.name not in [".env", ".gitignore"]:
                    continue
                if item.name in ["__pycache__", "node_modules", ".git", ".pytest_cache"]:
                    continue
                type_str = "DIR " if item.is_dir() else "FILE"
                size_str = f"{item.stat().st_size / 1024:.1f} KB" if item.is_file() else "-"
                entries.append(f"{type_str:4s} | {size_str:>8s} | {item.name}")

            return f"Contents of '{dir_path}' ({len(entries)} items):\n" + "\n".join(entries)
        except Exception as exc:
            return f"Error listing directory '{dir_path}': {exc}"

    def search_code(self, query: str, search_dir: str = ".") -> str:
        """Search text or symbol across files in the workspace."""
        target = self._resolve_path(search_dir)
        if not target.exists():
            return f"Error: Directory '{search_dir}' does not exist."

        matches = []
        try:
            # First try git grep if inside git repo
            git_res = subprocess.run(
                ["git", "grep", "-n", "-I", query],
                cwd=target,
                capture_output=True,
                text=True,
                check=False,
            )
            if git_res.returncode == 0 and git_res.stdout.strip():
                lines = git_res.stdout.strip().splitlines()[:50]
                return f"Found {len(lines)} matches via git grep:\n" + "\n".join(lines)

            # Fallback to python recursive search
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "node_modules", "models"]]
                for f in files:
                    if f.endswith((".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".yml", ".txt", ".sh", ".bat")):
                        fp = Path(root) / f
                        try:
                            text = fp.read_text(encoding="utf-8", errors="ignore")
                            if query.lower() in text.lower():
                                rel = fp.relative_to(self.workspace_path)
                                for idx, line in enumerate(text.splitlines()):
                                    if query.lower() in line.lower():
                                        matches.append(f"{rel}:{idx+1}: {line.strip()[:100]}")
                                        if len(matches) >= 30:
                                            break
                        except Exception:
                            continue
                if len(matches) >= 30:
                    break

            if not matches:
                return f"No matches found for '{query}' in '{search_dir}'."
            return f"Found {len(matches)} matches:\n" + "\n".join(matches)
        except Exception as exc:
            return f"Error searching code: {exc}"

    def run_command(self, command: str, timeout: int = 30) -> str:
        """Run terminal commands (like pytest, pip, git, npm) in the workspace."""
        cmd = command.strip()
        if not cmd:
            return "Error: Command cannot be empty."

        # Safety: block dangerous destruction commands
        lowered = cmd.lower()
        if "rm -rf /" in lowered or "format c:" in lowered:
            return "Error: Blocked potentially destructive system command."

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
            output = []
            if proc.stdout:
                output.append(proc.stdout.strip())
            if proc.stderr:
                output.append(f"[STDERR]\n{proc.stderr.strip()}")
            out_str = "\n".join(output) if output else "(No output)"
            return f"[Exit code {proc.returncode}]\n{out_str}"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as exc:
            return f"Error running command '{cmd}': {exc}"

    def git_status(self) -> str:
        """Get git status of workspace."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "--branch"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout.strip() or "Working tree clean."
        except Exception as exc:
            return f"Git error: {exc}"

    def git_diff(self) -> str:
        """Get git diff of uncommitted changes."""
        try:
            res = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                check=False,
            )
            diff = res.stdout.strip()
            if not diff:
                res2 = subprocess.run(
                    ["git", "diff"],
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                diff = res2.stdout.strip()
            return diff or "No changes detected."
        except Exception as exc:
            return f"Git diff error: {exc}"

    def web_search(self, query: str, max_results: int = 4) -> str:
        """Search the web using DuckDuckGo with Wikipedia fallback (100% free)."""
        query = (query or "").strip()
        if not query:
            return "Error: Empty search query."

        results = []
        # Try DuckDuckGo
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            ddgs = DDGS()
            raw = list(ddgs.text(query, max_results=max_results))
            for item in raw:
                title = item.get("title", "").strip()
                href = item.get("href", "").strip()
                body = item.get("body", "").strip()
                if href and (title or body):
                    results.append(f"• **{title}**\n  URL: {href}\n  Snippet: {body}")
        except Exception:
            pass

        # Fallback to Wikipedia API if needed
        if len(results) < 2:
            try:
                import requests
                headers = {"User-Agent": "ASTRA/3.0 (Autonomous Agent)"}
                url = "https://en.wikipedia.org/w/api.php"
                params = {"action": "opensearch", "search": query, "limit": max_results, "namespace": 0, "format": "json"}
                r = requests.get(url, params=params, headers=headers, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    titles = data[1] if len(data) > 1 else []
                    snippets = data[2] if len(data) > 2 else []
                    links = data[3] if len(data) > 3 else []
                    for t, s, l in zip(titles, snippets, links):
                        results.append(f"• **{t}** (Wikipedia)\n  URL: {l}\n  Snippet: {s or 'Wikipedia overview'}")
            except Exception:
                pass

        if not results:
            return f"No search results found for '{query}'."
        return "\n\n".join(results)


# Tool definitions for LLMs
TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the live web for error solutions, latest Python/library APIs, or documentation.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords or question"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents with line numbers from the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file"},
                "start_line": {"type": "integer", "description": "Optional start line (1-indexed)"},
                "end_line": {"type": "integer", "description": "Optional end line (1-indexed)"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with new content.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file"},
                "content": {"type": "string", "description": "Complete file content to write"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace a unique target snippet with replacement text in an existing file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file"},
                "target_snippet": {"type": "string", "description": "Exact text to find and replace"},
                "replacement_snippet": {"type": "string", "description": "Replacement text"},
            },
            "required": ["file_path", "target_snippet", "replacement_snippet"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and folders in a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "dir_path": {"type": "string", "description": "Relative path to folder (default: '.')"},
            },
        },
    },
    {
        "name": "search_code",
        "description": "Search code, functions, or text across the repository files.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term or regex"},
                "search_dir": {"type": "string", "description": "Directory to search in (default: '.')"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command (e.g. pytest, git, python, npm) to test or inspect.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Max timeout in seconds (default: 30)"},
            },
            "required": ["command"],
        },
    },
]
