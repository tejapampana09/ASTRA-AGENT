from __future__ import annotations

import tempfile
from pathlib import Path

from app.repository.scanner import RepositoryScanner


def test_repository_scanner_python_fastapi():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create requirements.txt and main.py
        (repo_path / "requirements.txt").write_text("fastapi>=0.115.0\nuvicorn\npytest\n", encoding="utf-8")
        (repo_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        (repo_path / "app").mkdir()
        (repo_path / "app" / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")

        summary = RepositoryScanner.scan(repo_path)
        assert "Python" in summary.languages
        assert summary.backend == "FastAPI"
        assert summary.test_framework == "pytest"
        assert summary.test_command == "pytest"
        assert "pip" in summary.package_managers
