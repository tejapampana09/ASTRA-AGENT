"""ASTRA V4 Workspace Manager and Project Detection Engine.

Provides deep project inspection, package manager detection, test/build/lint system discovery,
and secure filesystem tree representation.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ProjectType(str, Enum):
    PYTHON = "python"
    NODE = "node"
    TYPESCRIPT = "typescript"
    REACT = "react"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    UNKNOWN = "unknown"


@dataclass
class ProjectMetadata:
    workspace_path: str
    project_type: ProjectType
    project_types: List[ProjectType] = field(default_factory=list)
    package_manager: str = "none"
    test_command: Optional[str] = None
    build_command: Optional[str] = None
    lint_command: Optional[str] = None
    has_git: bool = False
    git_branch: str = ""
    total_files: int = 0
    key_manifests: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["project_type"] = self.project_type.value
        d["project_types"] = [pt.value if isinstance(pt, ProjectType) else str(pt) for pt in self.project_types]
        return d


class WorkspaceManager:
    """Manages workspace lifecycle, directory navigation, and project analysis."""

    def __init__(self, workspace_path: Optional[Path | str] = None):
        if workspace_path:
            self.workspace_path = Path(workspace_path).resolve()
        else:
            self.workspace_path = Path.cwd().resolve()
        self._cached_metadata: Optional[ProjectMetadata] = None

    def set_workspace(self, path: Path | str) -> bool:
        p = Path(path).resolve()
        if p.exists() and p.is_dir():
            self.workspace_path = p
            self._cached_metadata = None
            return True
        return False

    def validate(self) -> Tuple[bool, str]:
        if not self.workspace_path.exists():
            return False, f"Workspace path '{self.workspace_path}' does not exist."
        if not self.workspace_path.is_dir():
            return False, f"Workspace path '{self.workspace_path}' is not a directory."
        return True, "Valid workspace directory."

    def scan(self, force_refresh: bool = False) -> ProjectMetadata:
        """Scan workspace and identify project types, build tools, and test suites."""
        if self._cached_metadata and not force_refresh:
            return self._cached_metadata

        root = self.workspace_path
        detected_types: List[ProjectType] = []
        manifests: List[str] = []
        package_manager = "none"
        test_command = None
        build_command = None
        lint_command = None

        # Check Python
        has_py = any((root / f).exists() for f in ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"])
        if not has_py:
            # Check for any .py files in root or tests/
            has_py = bool(list(root.glob("*.py"))) or (root / "tests").exists()
        
        if has_py:
            detected_types.append(ProjectType.PYTHON)
            if (root / "pyproject.toml").exists():
                manifests.append("pyproject.toml")
            if (root / "requirements.txt").exists():
                manifests.append("requirements.txt")
            if (root / "Pipfile").exists():
                package_manager = "pipenv"
            elif (root / "poetry.lock").exists():
                package_manager = "poetry"
            else:
                package_manager = "pip"
            test_command = "python -m pytest"

        # Check Node / TypeScript / React
        pkg_json_path = root / "package.json"
        if pkg_json_path.exists():
            manifests.append("package.json")
            pkg_data = {}
            try:
                pkg_data = json.loads(pkg_json_path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass

            dependencies = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
            scripts = pkg_data.get("scripts", {})

            # Detect package manager
            if (root / "pnpm-lock.yaml").exists():
                package_manager = "pnpm"
            elif (root / "yarn.lock").exists():
                package_manager = "yarn"
            elif (root / "package-lock.json").exists():
                package_manager = "npm"
            elif package_manager == "none":
                package_manager = "npm"

            # Detect React
            if "react" in dependencies or "react-dom" in dependencies:
                detected_types.append(ProjectType.REACT)

            # Detect TypeScript
            if (root / "tsconfig.json").exists() or "typescript" in dependencies:
                detected_types.append(ProjectType.TYPESCRIPT)
            else:
                detected_types.append(ProjectType.NODE)

            # Determine scripts
            pm_prefix = package_manager if package_manager != "npm" else "npm run"
            if "test" in scripts:
                test_command = f"{package_manager} test" if package_manager != "npm" else "npm test"
            elif "jest" in dependencies or "vitest" in dependencies:
                test_command = "npx vitest run" if "vitest" in dependencies else "npx jest"

            if "build" in scripts:
                build_command = f"{pm_prefix} build"
            elif (root / "tsconfig.json").exists():
                build_command = "npx tsc --noEmit"

            if "lint" in scripts:
                lint_command = f"{pm_prefix} lint"

        # Check Rust
        if (root / "Cargo.toml").exists():
            detected_types.append(ProjectType.RUST)
            manifests.append("Cargo.toml")
            package_manager = "cargo"
            test_command = "cargo test"
            build_command = "cargo build"

        # Check Go
        if (root / "go.mod").exists():
            detected_types.append(ProjectType.GO)
            manifests.append("go.mod")
            package_manager = "go"
            test_command = "go test ./..."
            build_command = "go build ./..."

        # Check Java
        if (root / "pom.xml").exists():
            detected_types.append(ProjectType.JAVA)
            manifests.append("pom.xml")
            package_manager = "maven"
            test_command = "mvn test"
            build_command = "mvn compile"
        elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            detected_types.append(ProjectType.JAVA)
            manifests.append("build.gradle")
            package_manager = "gradle"
            test_command = "gradle test"
            build_command = "gradle build"

        # Primary project type
        primary_type = detected_types[0] if detected_types else ProjectType.UNKNOWN

        # Git status check
        has_git = (root / ".git").exists()
        git_branch = ""
        if has_git:
            try:
                res = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                git_branch = res.stdout.strip()
            except Exception:
                pass

        # Count files
        total_files = 0
        try:
            for _, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "__pycache__", "dist", "build", "target"]]
                total_files += len(files)
        except Exception:
            pass

        meta = ProjectMetadata(
            workspace_path=str(self.workspace_path),
            project_type=primary_type,
            project_types=detected_types or [ProjectType.UNKNOWN],
            package_manager=package_manager,
            test_command=test_command,
            build_command=build_command,
            lint_command=lint_command,
            has_git=has_git,
            git_branch=git_branch,
            total_files=total_files,
            key_manifests=manifests,
        )

        self._cached_metadata = meta
        return meta

    def get_file_tree(self, current_dir: Optional[Path] = None, depth: int = 0, max_depth: int = 4) -> List[Dict[str, Any]]:
        """Return directory tree structure formatted for UI tree views."""
        target = current_dir or self.workspace_path
        if depth >= max_depth or not target.is_dir():
            return []

        ignored = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode", "dist", "build", "target"}
        items: List[Dict[str, Any]] = []

        try:
            entries = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            for entry in entries:
                if entry.name in ignored or entry.name.startswith(".pytest_cache"):
                    continue

                rel_path = str(entry.relative_to(self.workspace_path)).replace("\\", "/")
                if entry.is_dir():
                    children = self.get_file_tree(entry, depth=depth + 1, max_depth=max_depth)
                    items.append({
                        "name": entry.name,
                        "path": rel_path,
                        "type": "directory",
                        "children": children,
                    })
                else:
                    items.append({
                        "name": entry.name,
                        "path": rel_path,
                        "type": "file",
                        "size": entry.stat().st_size,
                    })
        except Exception:
            pass

        return items
