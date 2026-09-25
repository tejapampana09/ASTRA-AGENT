from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.logging import logger


@dataclass
class RepositorySummary:
    languages: List[str] = field(default_factory=list)
    frontend: Optional[str] = None
    backend: Optional[str] = None
    database: Optional[str] = None
    package_managers: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    test_framework: Optional[str] = None
    test_command: Optional[str] = None
    build_command: Optional[str] = None
    config_files: List[str] = field(default_factory=list)
    important_directories: List[str] = field(default_factory=list)
    git_branch: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "languages": self.languages,
            "frontend": self.frontend,
            "backend": self.backend,
            "database": self.database,
            "package_managers": self.package_managers,
            "dependencies": self.dependencies[:50],
            "entry_points": self.entry_points,
            "test_framework": self.test_framework,
            "test_command": self.test_command,
            "build_command": self.build_command,
            "config_files": self.config_files,
            "important_directories": self.important_directories,
            "git_branch": self.git_branch,
        }


class RepositoryScanner:
    """Inspects and detects project architecture, frameworks, and commands without hallucination."""

    @classmethod
    def scan(cls, repo_path: Path) -> RepositorySummary:
        summary = RepositorySummary()
        if not repo_path.exists():
            return summary

        # 1. Detect Config Files
        common_configs = [
            "package.json", "requirements.txt", "pyproject.toml", "Pipfile",
            "Cargo.toml", "go.mod", "Dockerfile", "docker-compose.yml",
            "tsconfig.json", "pytest.ini", "vite.config.ts"
        ]
        for cfg in common_configs:
            if (repo_path / cfg).exists():
                summary.config_files.append(cfg)

        # 2. Detect Package Managers & Dependencies
        languages = set()
        if (repo_path / "requirements.txt").exists():
            summary.package_managers.append("pip")
            languages.add("Python")
            try:
                deps = (repo_path / "requirements.txt").read_text(encoding="utf-8").splitlines()
                summary.dependencies.extend([d.strip() for d in deps if d.strip() and not d.startswith("#")])
            except Exception:
                pass

        if (repo_path / "pyproject.toml").exists():
            languages.add("Python")
            if "pip" not in summary.package_managers:
                summary.package_managers.append("poetry/flit/uv")

        if (repo_path / "package.json").exists():
            languages.add("JavaScript/TypeScript")
            summary.package_managers.append("npm")
            try:
                pkg_data = json.loads((repo_path / "package.json").read_text(encoding="utf-8"))
                deps = pkg_data.get("dependencies", {})
                dev_deps = pkg_data.get("devDependencies", {})
                all_deps = list(deps.keys()) + list(dev_deps.keys())
                summary.dependencies.extend(all_deps)

                # Frontend detection
                if "react" in deps:
                    summary.frontend = "React"
                elif "vue" in deps:
                    summary.frontend = "Vue"
                elif "next" in deps:
                    summary.frontend = "Next.js"

                scripts = pkg_data.get("scripts", {})
                if "test" in scripts:
                    summary.test_command = "npm test"
                    summary.test_framework = "vitest/jest"
                if "build" in scripts:
                    summary.build_command = "npm run build"
            except Exception:
                pass

        # 3. Detect Backend Frameworks
        dep_str = " ".join(summary.dependencies).lower()
        if "fastapi" in dep_str:
            summary.backend = "FastAPI"
        elif "django" in dep_str:
            summary.backend = "Django"
        elif "flask" in dep_str:
            summary.backend = "Flask"
        elif "express" in dep_str:
            summary.backend = "Express"

        # 4. Detect Database
        if "postgres" in dep_str or "psycopg" in dep_str or "asyncpg" in dep_str:
            summary.database = "PostgreSQL"
        elif "sqlite" in dep_str:
            summary.database = "SQLite"
        elif "mysql" in dep_str:
            summary.database = "MySQL"
        elif "redis" in dep_str:
            summary.database = "Redis"

        # 5. Detect Test Commands for Python
        if "pytest" in dep_str or (repo_path / "pytest.ini").exists() or list(repo_path.glob("**/test_*.py")):
            summary.test_framework = "pytest"
            summary.test_command = "pytest"

        # 6. Important Directories
        for candidate in ["src", "app", "backend", "frontend", "tests", "docs", "pkg", "cmd"]:
            if (repo_path / candidate).is_dir():
                summary.important_directories.append(candidate)

        # 7. Git Branch
        if (repo_path / ".git").exists():
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False
                )
                if res.returncode == 0:
                    summary.git_branch = res.stdout.strip()
            except Exception:
                pass

        summary.languages = sorted(list(languages))
        logger.info(f"Repository scanned: {summary.to_dict()}")
        return summary
