"""ASTRA V4 Tool System: Registry, Security Sandbox, and Central Tool Executor.

Enforces:
1. Workspace containment & path traversal protection
2. Secret protection (.env, private keys, credentials)
3. Three-tier permission levels (SAFE, MODERATE, DANGEROUS)
4. Approval callbacks for dangerous/destructive commands
5. Structured execution results with exit codes, timing, and cancellation
"""
from __future__ import annotations

import enum
import fnmatch
import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class PermissionLevel(str, enum.Enum):
    SAFE = "SAFE"
    MODERATE = "MODERATE"
    DANGEROUS = "DANGEROUS"


@dataclass
class ToolResult:
    """Standardized output of any tool execution."""
    success: bool
    output: str
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    command: Optional[str] = None
    exit_code: Optional[int] = None
    timed_out: bool = False

    def to_string(self) -> str:
        if self.output and self.error:
            return f"{self.output}\n[Error: {self.error}]"
        if self.error:
            return f"Error: {self.error}"
        return self.output or "(No output)"


class SecurityManager:
    """Filesystem boundary enforcer and dangerous command classifier."""

    SENSITIVE_PATTERNS = [
        ".env",
        ".env.*",
        "*.pem",
        "*.key",
        "*.pkcs12",
        "id_rsa",
        "id_rsa.*",
        "id_ed25519",
        "id_ed25519.*",
        "credentials.json",
        "service_account*.json",
        "*token*",
        "*secret*",
    ]

    DANGEROUS_COMMAND_PATTERNS = [
        r"rm\s+-rf?\s+[\/\*]",
        r"del\s+/[fqs]",
        r"rmdir\s+/[sq]",
        r"format\s+[a-z]:",
        r"git\s+reset\s+--hard",
        r"git\s+clean\s+-[a-z]*f",
        r"git\s+push\s+.*--force",
        r"git\s+branch\s+-D",
        r"mkfs",
        r"dd\s+if=",
        r":\(\)\s*\{\s*:\|:&\s*\};:", # fork bomb
        r"chmod\s+-R\s+777\s+/",
        r"shutdown",
        r"reboot",
    ]

    MODERATE_COMMAND_PATTERNS = [
        r"npm\s+install",
        r"pip\s+install",
        r"cargo\s+install",
        r"git\s+checkout",
        r"git\s+merge",
        r"git\s+rebase",
        r"docker\s+run",
        r"docker-compose",
    ]

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path.resolve()

    def resolve_and_validate_path(self, target_path: str, allow_sensitive_read: bool = False) -> Path:
        """Resolve a path and ensure it strictly stays within workspace_path without traversal."""
        if not target_path:
            raise ValueError("File path cannot be empty.")

        # Check raw string for obvious path traversal escapes
        normalized_str = target_path.replace("\\", "/")
        if normalized_str.startswith("../") or "/../" in normalized_str or normalized_str == "..":
            p = (self.workspace_path / target_path).resolve()
        else:
            p = Path(target_path)
            if not p.is_absolute():
                p = (self.workspace_path / p).resolve()
            else:
                p = p.resolve()

        # Strict boundary check
        try:
            p.relative_to(self.workspace_path)
        except ValueError:
            raise PermissionError(
                f"Security Violation: Path '{target_path}' resolves to '{p}', "
                f"which is outside active workspace '{self.workspace_path}'."
            )

        # Check secret protection
        if not allow_sensitive_read:
            file_name = p.name.lower()
            for pattern in self.SENSITIVE_PATTERNS:
                if fnmatch.fnmatch(file_name, pattern):
                    raise PermissionError(
                        f"Security Protection: Direct access to sensitive file '{p.name}' is restricted. "
                        "Sensitive configuration files (.env, keys, credentials) are protected."
                    )

        return p

    def classify_command(self, cmd: str) -> PermissionLevel:
        """Determine permission tier of command."""
        cmd_clean = cmd.strip()
        
        for pat in self.DANGEROUS_COMMAND_PATTERNS:
            if re.search(pat, cmd_clean, re.IGNORECASE):
                return PermissionLevel.DANGEROUS

        for pat in self.MODERATE_COMMAND_PATTERNS:
            if re.search(pat, cmd_clean, re.IGNORECASE):
                return PermissionLevel.MODERATE

        return PermissionLevel.SAFE


class ToolExecutor:
    """Executes workspace actions safely with full tracking and security controls."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = (workspace_path or Path.cwd()).resolve()
        self.security = SecurityManager(self.workspace_path)

    def read_file(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Read text from a file with optional line ranges."""
        try:
            target = self.security.resolve_and_validate_path(file_path)
        except Exception as exc:
            return f"Error: {exc}"

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
        """Create or overwrite a file with given content."""
        try:
            target = self.security.resolve_and_validate_path(file_path)
        except Exception as exc:
            return f"Error: {exc}"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to '{file_path}'."
        except Exception as exc:
            return f"Error writing file '{file_path}': {exc}"

    def create_file(self, file_path: str, content: str = "") -> str:
        """Explicitly create a new file (errors if file already exists)."""
        try:
            target = self.security.resolve_and_validate_path(file_path)
        except Exception as exc:
            return f"Error: {exc}"

        if target.exists():
            return f"Error: File already exists at '{file_path}'. Use write_file or edit_file instead."

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Successfully created new file '{file_path}'."
        except Exception as exc:
            return f"Error creating file '{file_path}': {exc}"

    def delete_file(self, file_path: str) -> str:
        """Delete a file safely within workspace."""
        try:
            target = self.security.resolve_and_validate_path(file_path)
        except Exception as exc:
            return f"Error: {exc}"

        if not target.exists():
            return f"Error: File '{file_path}' does not exist."
        if target.is_dir():
            return f"Error: Cannot delete directory '{file_path}' with delete_file."

        try:
            target.unlink()
            return f"Successfully deleted file '{file_path}'."
        except Exception as exc:
            return f"Error deleting file '{file_path}': {exc}"

    def edit_file(self, file_path: str, target_snippet: str, replacement_snippet: str) -> str:
        """Replace a specific unique snippet in an existing file."""
        try:
            target = self.security.resolve_and_validate_path(file_path)
        except Exception as exc:
            return f"Error: {exc}"

        if not target.exists():
            return f"Error: File does not exist at '{file_path}'"

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            if target_snippet not in content:
                # Provide helpful diagnostic
                return (
                    f"Error: Target snippet not found in '{file_path}'. "
                    "Ensure snippet matches exact whitespace and indentation."
                )

            count = content.count(target_snippet)
            if count > 1:
                return (
                    f"Warning: Target snippet occurs {count} times in '{file_path}'. "
                    "Please provide more context lines to ensure unique replacement."
                )

            new_content = content.replace(target_snippet, replacement_snippet, 1)
            target.write_text(new_content, encoding="utf-8")
            return f"Successfully updated '{file_path}' (replaced 1 instance)."
        except Exception as exc:
            return f"Error editing file '{file_path}': {exc}"

    def list_dir(self, dir_path: str = ".") -> str:
        """List files and directories in workspace directory."""
        try:
            target = self.security.resolve_and_validate_path(dir_path, allow_sensitive_read=True)
        except Exception as exc:
            return f"Error: {exc}"

        if not target.exists():
            return f"Error: Path '{dir_path}' does not exist."
        if not target.is_dir():
            return f"Error: Path '{dir_path}' is not a directory."

        try:
            entries = []
            for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                name = item.name
                if name in [".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv", ".idea"]:
                    continue
                type_str = "DIR " if item.is_dir() else "FILE"
                size_str = f"{item.stat().st_size / 1024:.1f} KB" if item.is_file() else "-"
                entries.append(f"{type_str:4s} | {size_str:>8s} | {name}")

            return f"Contents of '{dir_path}' ({len(entries)} items):\n" + "\n".join(entries)
        except Exception as exc:
            return f"Error listing directory '{dir_path}': {exc}"

    def search_code(self, query: str, search_dir: str = ".") -> str:
        """Fast repository search with smart directory filtering."""
        try:
            target = self.security.resolve_and_validate_path(search_dir, allow_sensitive_read=True)
        except Exception as exc:
            return f"Error: {exc}"

        if not target.exists():
            return f"Error: Directory '{search_dir}' does not exist."

        matches = []
        # Attempt git grep first if git repo exists
        try:
            git_res = subprocess.run(
                ["git", "grep", "-n", "-I", query],
                cwd=target,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if git_res.returncode == 0 and git_res.stdout.strip():
                lines = git_res.stdout.strip().splitlines()[:40]
                return f"Found {len(lines)} matches via git grep:\n" + "\n".join(lines)
        except Exception:
            pass

        # Python fallback search
        ignored_dirs = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", "models", ".pytest_cache"}
        valid_extensions = (".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".toml", ".yaml", ".yml", ".rs", ".go", ".java", ".c", ".cpp")
        
        try:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ignored_dirs]
                for f in files:
                    if f.endswith(valid_extensions):
                        fp = Path(root) / f
                        try:
                            text = fp.read_text(encoding="utf-8", errors="ignore")
                            if query.lower() in text.lower():
                                rel = fp.relative_to(self.workspace_path)
                                for idx, line in enumerate(text.splitlines()):
                                    if query.lower() in line.lower():
                                        matches.append(f"{rel}:{idx+1}: {line.strip()[:120]}")
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

    def run_command(
        self,
        command: str,
        timeout: int = 45,
        on_output: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> str:
        """Run shell command in workspace with timeout, streaming, and cancellation."""
        cmd = command.strip()
        if not cmd:
            return "Error: Command cannot be empty."

        perm = self.security.classify_command(cmd)
        if perm == PermissionLevel.DANGEROUS:
            return f"Error: Command '{cmd}' classified as DANGEROUS and was blocked."

        start_time = time.time()
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.workspace_path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            stdout_lines = []
            stderr_lines = []

            # Non-blocking poll with timeout & cancellation
            while True:
                if cancel_check and cancel_check():
                    proc.kill()
                    return "Error: Command execution cancelled by user."

                if time.time() - start_time > timeout:
                    proc.kill()
                    return f"Error: Command timed out after {timeout} seconds."

                ret = proc.poll()
                if ret is not None:
                    break
                time.sleep(0.05)

            stdout_data, stderr_data = proc.communicate(timeout=5)
            
            output = []
            if stdout_data and stdout_data.strip():
                output.append(stdout_data.strip())
            if stderr_data and stderr_data.strip():
                output.append(f"[STDERR]\n{stderr_data.strip()}")

            out_str = "\n".join(output) if output else "(No output)"
            return f"[Exit code {proc.returncode}]\n{out_str}"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as exc:
            return f"Error executing command '{cmd}': {exc}"

    def git_status(self) -> str:
        """Get git status of workspace."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "--branch"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
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
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            diff = res.stdout.strip()
            if not diff:
                res2 = subprocess.run(
                    ["git", "diff"],
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                diff = res2.stdout.strip()
            return diff or "No changes detected."
        except Exception as exc:
            return f"Git diff error: {exc}"

    def git_branch(self) -> str:
        """Get current git branch name."""
        try:
            res = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            return res.stdout.strip() or "main"
        except Exception:
            return "unknown"

    def git_log(self, max_commits: int = 5) -> str:
        """Get recent git commits."""
        try:
            res = subprocess.run(
                ["git", "log", f"-{max_commits}", "--oneline"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout.strip() or "No commit history."
        except Exception as exc:
            return f"Git log error: {exc}"

    def web_search(self, query: str, max_results: int = 4) -> str:
        """Search the web using DuckDuckGo or Wikipedia."""
        query = (query or "").strip()
        if not query:
            return "Error: Empty search query."

        results = []
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            ddgs = DDGS()
            raw = list(ddgs.text(query, max_results=max_results))
            for item in raw:
                title = item.get("title", "")
                snippet = item.get("body", "")
                link = item.get("href", "")
                results.append(f"### {title}\n{snippet}\nURL: {link}")
            if results:
                return f"Web Search Results for '{query}':\n\n" + "\n\n".join(results)
        except Exception:
            pass

        return f"No web search results available for '{query}'."


# Schema definitions for tools
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read contents of a file within the workspace. Optional start_line and end_line parameters allow viewing specific line slices.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file in workspace."},
                "start_line": {"type": "integer", "description": "Starting line number (1-indexed)."},
                "end_line": {"type": "integer", "description": "Ending line number (1-indexed)."},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or completely overwrite a file with new content.",
        "permission": PermissionLevel.MODERATE,
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file in workspace."},
                "content": {"type": "string", "description": "Full new file content."},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "create_file",
        "description": "Create a new file in the workspace. Fails if file already exists.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path of new file."},
                "content": {"type": "string", "description": "Initial content of new file."},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from the workspace.",
        "permission": PermissionLevel.MODERATE,
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file to delete."},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "edit_file",
        "description": "Perform surgical edit by replacing target_snippet with replacement_snippet in an existing file.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file in workspace."},
                "target_snippet": {"type": "string", "description": "Exact text snippet to replace."},
                "replacement_snippet": {"type": "string", "description": "Replacement code snippet."},
            },
            "required": ["file_path", "target_snippet", "replacement_snippet"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and directories within a workspace directory.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {
                "dir_path": {"type": "string", "description": "Directory relative to workspace root. Default is '.'"},
            },
        },
    },
    {
        "name": "search_code",
        "description": "Search text, keywords, or function symbols across files in the workspace.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search string or symbol name."},
                "search_dir": {"type": "string", "description": "Directory to search within (default '.')."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_command",
        "description": "Execute terminal commands such as test suites (pytest, npm test), build commands, linters, or git in the workspace.",
        "permission": PermissionLevel.MODERATE,
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command string to execute."},
                "timeout": {"type": "integer", "description": "Maximum execution time in seconds (default 45)."},
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_status",
        "description": "Check current Git status, branch, and modified files in the workspace.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "git_diff",
        "description": "Get git diff of uncommitted changes in the workspace.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "web_search",
        "description": "Search the live web for technical documentation, library APIs, or solutions.",
        "permission": PermissionLevel.SAFE,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query terms."},
            },
            "required": ["query"],
        },
    },
]


class ToolRegistry:
    """Registry managing tool definitions, validation, permissions, and execution dispatch."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = (workspace_path or Path.cwd()).resolve()
        self.executor = ToolExecutor(self.workspace_path)
        self.tools: Dict[str, Dict[str, Any]] = {t["name"]: t for t in TOOL_DEFINITIONS}

    def get_definitions(self) -> List[Dict[str, Any]]:
        return TOOL_DEFINITIONS

    def execute(
        self,
        name: str,
        args: Dict[str, Any],
        approval_callback: Optional[Callable[[str, str, Dict[str, Any]], bool]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ToolResult:
        """Central executor with validation, permission check, approval, and execution."""
        start_time = time.time()
        
        if name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool '{name}'",
                duration_ms=(time.time() - start_time) * 1000,
            )

        tool_def = self.tools[name]
        permission: PermissionLevel = tool_def.get("permission", PermissionLevel.SAFE)

        # Dynamic permission check for run_command
        if name == "run_command":
            cmd = args.get("command", "")
            cmd_perm = self.executor.security.classify_command(cmd)
            if cmd_perm == PermissionLevel.DANGEROUS:
                permission = PermissionLevel.DANGEROUS

        # If DANGEROUS, require explicit approval
        if permission == PermissionLevel.DANGEROUS:
            approved = False
            if approval_callback:
                approved = approval_callback(name, f"Tool '{name}' requested with args: {args}", args)
            if not approved:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Execution blocked: Command or action requires user approval.",
                    duration_ms=(time.time() - start_time) * 1000,
                )

        # Execute handler
        try:
            if name == "read_file":
                out = self.executor.read_file(
                    file_path=args.get("file_path", ""),
                    start_line=args.get("start_line"),
                    end_line=args.get("end_line"),
                )
            elif name == "write_file":
                out = self.executor.write_file(
                    file_path=args.get("file_path", ""),
                    content=args.get("content", ""),
                )
            elif name == "create_file":
                out = self.executor.create_file(
                    file_path=args.get("file_path", ""),
                    content=args.get("content", ""),
                )
            elif name == "delete_file":
                out = self.executor.delete_file(
                    file_path=args.get("file_path", ""),
                )
            elif name == "edit_file":
                out = self.executor.edit_file(
                    file_path=args.get("file_path", ""),
                    target_snippet=args.get("target_snippet", ""),
                    replacement_snippet=args.get("replacement_snippet", ""),
                )
            elif name == "list_dir":
                out = self.executor.list_dir(dir_path=args.get("dir_path", "."))
            elif name == "search_code":
                out = self.executor.search_code(
                    query=args.get("query", ""),
                    search_dir=args.get("search_dir", "."),
                )
            elif name == "run_command":
                out = self.executor.run_command(
                    command=args.get("command", ""),
                    timeout=args.get("timeout", 45),
                    cancel_check=cancel_check,
                )
            elif name == "git_status":
                out = self.executor.git_status()
            elif name == "git_diff":
                out = self.executor.git_diff()
            elif name == "web_search":
                out = self.executor.web_search(
                    query=args.get("query", ""),
                )
            else:
                out = f"Error: Tool '{name}' handler not implemented."

            is_err = out.startswith("Error:") or out.startswith("Security Violation:") or out.startswith("Security Protection:")
            duration = (time.time() - start_time) * 1000
            return ToolResult(
                success=not is_err,
                output=out if not is_err else "",
                error=out if is_err else None,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                output="",
                error=str(exc),
                duration_ms=duration,
            )
