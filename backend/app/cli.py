from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

# Suppress python runtime warnings and thread noise
warnings.filterwarnings("ignore")
os.environ["ASTRA_CLI_MODE"] = "1"
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def silence_background_logging():
    """Route all internal library and system logs to astra_agent.log; keep terminal pristine."""
    log_file = Path.cwd() / "astra_agent.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))

    noisy_loggers = [
        "",
        "astra",
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.dialects",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        "litellm",
        "LiteLLM",
        "LiteLLM Router",
        "LiteLLM Proxy",
        "httpx",
        "httpcore",
        "urllib3",
        "openhands",
        "asyncio",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
    ]

    for name in noisy_loggers:
        lg = logging.getLogger(name)
        lg.handlers = [file_handler]
        lg.setLevel(logging.WARNING)
        lg.propagate = False

    try:
        import litellm
        litellm.suppress_debug_info = True
        litellm.set_verbose = False
    except Exception:
        pass

# Initialize quiet environment immediately
silence_background_logging()

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

CONVERSATIONAL_PROMPTS = {
    "hi": "👋 Hello! I am ASTRA, your autonomous software engineering agent. Tell me what bug to investigate, feature to implement, or tests to run!",
    "hello": "👋 Hello! I am ASTRA, your autonomous software engineering agent. Tell me what bug to investigate, feature to implement, or tests to run!",
    "hey": "👋 Hey there! Ready to write, test, or refactor code. What should we work on?",
    "who are you": "🧠 I am ASTRA 2.0 — an Autonomous Software Engineering Agent. I can inspect repositories, plan changes, write code, run verification tests, debug failures, and create git commits completely autonomously.",
    "who are you?": "🧠 I am ASTRA 2.0 — an Autonomous Software Engineering Agent. I can inspect repositories, plan changes, write code, run verification tests, debug failures, and create git commits completely autonomously.",
    "what can you do": "🛠️ **What I can do:**\n- 🔍 Investigate codebase architecture & dependencies\n- 📝 Plan multi-step modifications\n- 💻 Edit and create files in isolated workspaces\n- 🧪 Run test suites (pytest/unittest) and observe real test output\n- 🔁 Autonomously debug and replan if tests fail\n- 📦 Create conventional git commits and prepare pull requests",
    "what can you do?": "🛠️ **What I can do:**\n- 🔍 Investigate codebase architecture & dependencies\n- 📝 Plan multi-step modifications\n- 💻 Edit and create files in isolated workspaces\n- 🧪 Run test suites (pytest/unittest) and observe real test output\n- 🔁 Autonomously debug and replan if tests fail\n- 📦 Create conventional git commits and prepare pull requests",
}


class AstraCLI:
    def __init__(
        self,
        model: Optional[str] = None,
        mode: str = "autonomous",
        repo_path: Optional[str] = None,
    ):
        silence_background_logging()

        # Auto-detect best model: default to Gemini if API key present, else Ollama
        has_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY"))
        if model:
            if "gemini" in model.lower() or "cloud" in model.lower():
                self.model = "gemini/gemini-2.5-flash"
            else:
                self.model = "ollama/qwen2.5-coder:3b"
        else:
            self.model = "gemini/gemini-2.5-flash" if has_gemini else "ollama/qwen2.5-coder:3b"

        self.mode = mode
        self.repo_path = repo_path or str(Path.cwd().resolve())

        from app.runtime.lifecycle import TaskLifecycleManager
        from app.runtime.session import conversation_manager, AgentSession
        self._conversation_manager = conversation_manager
        self.lifecycle = TaskLifecycleManager()
        self.session: AgentSession = conversation_manager.create_session(
            repository_path=self.repo_path,
            model=self.model,
            mode=self.mode,
            initial_title="Terminal CLI Session",
        )

    def print_header(self):
        model_display = "⚡ Gemini Flash (gemini-2.5-flash)" if "gemini" in self.model else "🦙 Ollama Local (qwen2.5-coder:3b)"
        repo_name = Path(self.repo_path).name or self.repo_path

        console.print("\n[bold cyan]✦ ASTRA 2.0[/bold cyan] [dim]— Autonomous Coding Agent[/dim]")
        console.print(f"  [dim]• Model:[/dim]      [bold]{model_display}[/bold]")
        console.print(f"  [dim]• Mode:[/dim]       [bold]{self.mode.capitalize()}[/bold] (auto-verify & commit)")
        console.print(f"  [dim]• Workspace:[/dim]  [cyan]{self.repo_path}[/cyan] ({repo_name})")
        console.print("  [dim]• Commands:[/dim]   /model, /mode, /diff, /history, /help, /exit\n")

    async def execute_goal(self, goal: str) -> None:
        """Executes a goal cleanly with live terminal activity indicators like Gemini CLI / Claude Code."""
        # Check for simple conversational messages first
        normalized = goal.strip().lower()
        if normalized in CONVERSATIONAL_PROMPTS:
            console.print(f"\n[bold green]ASTRA:[/bold green] {CONVERSATIONAL_PROMPTS[normalized]}\n")
            return

        silence_background_logging()
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        self._conversation_manager.add_user_message(self.session.id, goal, task_id=task_id)
        contextual_goal = self._conversation_manager.build_contextual_prompt(self.session.id, goal)

        console.print(f"\n[bold green]You:[/bold green] {goal}")
        console.print(f"[dim]● Task [bold]{task_id}[/bold] initiated[/dim]")

        task_info = self.lifecycle.create_task(
            task_id=task_id,
            goal=contextual_goal,
            repository_path=self.repo_path,
            model=self.model,
            mode=self.mode,
        )

        if self.session.workspace_path:
            task_info["workspace_path"] = self.session.workspace_path

        from app.runtime.events import central_event_bus
        event_queue = central_event_bus.subscribe(task_id)
        agent_task = asyncio.create_task(self.lifecycle.run_task_async(task_id))

        with console.status("[bold cyan]ASTRA is analyzing repository...[/bold cyan]", spinner="dots") as status:
            try:
                while not agent_task.done() or not event_queue.empty():
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.15)
                    except asyncio.TimeoutError:
                        continue

                    ev_type = str(event.event_type)
                    msg = event.message
                    payload = event.payload or {}

                    if ev_type in ["PLANNING_STARTED", "PLANNING"]:
                        status.update("[bold magenta]Investigating codebase architecture & planning...[/bold magenta]")

                    elif ev_type in ["PLAN_GENERATED"]:
                        status.stop()
                        steps = payload.get("steps", [])
                        console.print("\n[bold magenta]📋 Plan:[/bold magenta]")
                        for idx, step in enumerate(steps, 1):
                            console.print(f"   [cyan]{idx}.[/cyan] {step}")
                        console.print()
                        status.start()
                        status.update("[bold sky_blue1]Executing planned actions...[/bold sky_blue1]")

                    elif ev_type in ["TOOL_CALL_STARTED"]:
                        tool = payload.get("tool", "")
                        cmd = payload.get("command", "") or msg
                        cmd_display = cmd.replace("\n", " ").strip()
                        if len(cmd_display) > 80:
                            cmd_display = cmd_display[:77] + "..."
                        status.update(f"[bold yellow]Running:[/bold yellow] [dim]{tool}[/dim] {cmd_display}")

                    elif ev_type in ["FILE_CHANGED"]:
                        status.stop()
                        path = payload.get("path", "")
                        op = payload.get("operation", "modified")
                        console.print(f"  [bold green]✓[/bold green] [green]{op.capitalize()}:[/green] [bold cyan]{path}[/bold cyan]")
                        status.start()

                    elif ev_type in ["TEST_STARTED"]:
                        cmd = payload.get("command", "pytest")
                        status.update(f"[bold yellow]Running test verification ({cmd})...[/bold yellow]")

                    elif ev_type in ["TEST_COMPLETED"]:
                        status.stop()
                        passed = payload.get("passed", 0)
                        failed = payload.get("failed", 0)
                        if failed > 0:
                            console.print(f"  [bold red]✗ Tests:[/bold red] [red]{failed} failed[/red], [green]{passed} passed[/green]")
                        else:
                            console.print(f"  [bold green]✓ Tests:[/bold green] [green]All {passed} passed clean[/green]")
                        status.start()

                    elif ev_type in ["DEBUG_STARTED", "HYPOTHESIS_FORMULATED", "REPLAN_TRIGGERED"]:
                        status.update(f"[bold orange3]Self-correcting:[/bold orange3] {msg[:60]}...")

                    elif ev_type in ["AUDIT_COMPLETED"]:
                        status.update(f"[bold cyan]Auditing changes...[/bold cyan]")

                    elif ev_type in ["COMMIT_CREATED"]:
                        status.stop()
                        sha = payload.get("sha", "")[:7]
                        console.print(f"  [bold green]📦 Commit:[/bold green] [cyan]{sha}[/cyan] • {msg}")
                        status.start()

                    elif ev_type in ["PUSH_COMPLETED", "PR_CREATED"]:
                        status.stop()
                        console.print(f"  [bold blue]🚀 Git:[/bold blue] {msg}")
                        status.start()

                    elif ev_type in ["APPROVAL_REQUIRED"]:
                        status.stop()
                        console.print(Panel(
                            f"[bold yellow]APPROVAL REQUIRED[/bold yellow]\n{msg}",
                            border_style="yellow"
                        ))
                        choice = input("  Authorize execution? [y/N]: ").strip().lower()
                        if choice in ["y", "yes"]:
                            await self.lifecycle.resume_task_after_approval(task_id, approved=True)
                        else:
                            await self.lifecycle.resume_task_after_approval(task_id, approved=False)
                        status.start()

                    elif ev_type in ["TASK_COMPLETED"]:
                        status.stop()
                        console.print(f"\n[bold green]✦ Task Completed Successfully[/bold green]\n")
                        status.start()

                    elif ev_type in ["TASK_FAILED"]:
                        status.stop()
                        console.print(f"\n[bold red]✗ Task Incomplete[/bold red]: {msg}\n")
                        status.start()

                await agent_task

            except asyncio.CancelledError:
                self.lifecycle.cancel_task(task_id)
                console.print("\n[yellow]Task cancelled.[/yellow]")
            finally:
                central_event_bus.unsubscribe(task_id, event_queue)

        # Retrieve and display clean outcome
        task_data = self.lifecycle.get_task(task_id)
        if task_data and task_data.get("workspace_path"):
            self.session.workspace_path = task_data["workspace_path"]

        report = (task_data or {}).get("final_report") or {}
        evidence = report.get("evidence") or {}
        tests = evidence.get("tests") or {}
        files = evidence.get("files_changed") or []

        if files or tests.get("passed", 0) > 0 or report.get("commit"):
            result_items = []
            if tests.get("passed", 0) > 0:
                result_items.append(f"[green]{tests['passed']} tests passed[/green]")
            if files:
                result_items.append(f"[cyan]{len(files)} files modified[/cyan]")
            if report.get("commit"):
                result_items.append(f"commit [bold]{report['commit'].get('commit_sha', '')[:7]}[/bold]")
            console.print(f"[dim]Summary: {', '.join(result_items)}[/dim]\n")

    async def run_repl(self) -> None:
        """Interactive REPL matching Gemini CLI / Claude Code styling."""
        self.print_header()

        while True:
            try:
                console.print("[bold cyan]astra > [/bold cyan]", end="")
                user_input = input().strip()

                if not user_input:
                    continue

                if user_input in ["/exit", "/quit", "exit", "quit"]:
                    console.print("[dim]Exiting ASTRA. Bye![/dim]\n")
                    break

                elif user_input == "/help":
                    self.show_help()
                    continue

                elif user_input.startswith("/model"):
                    parts = user_input.split()
                    if len(parts) > 1 and parts[1].lower() in ["ollama", "qwen", "local"]:
                        self.model = "ollama/qwen2.5-coder:3b"
                        console.print("[green]Switched model to:[/green] 🦙 Ollama Local (qwen2.5-coder:3b)\n")
                    elif len(parts) > 1 and parts[1].lower() in ["gemini", "cloud", "flash"]:
                        self.model = "gemini/gemini-2.5-flash"
                        console.print("[green]Switched model to:[/green] ⚡ Gemini Flash (gemini-2.5-flash)\n")
                    else:
                        console.print(f"[dim]Active: {self.model}. Usage: /model [gemini|ollama][/dim]\n")
                    continue

                elif user_input.startswith("/mode"):
                    parts = user_input.split()
                    if len(parts) > 1 and parts[1].lower() in ["auto", "autonomous"]:
                        self.mode = "autonomous"
                        console.print("[green]Switched mode to:[/green] 🚀 Autonomous\n")
                    elif len(parts) > 1 and parts[1].lower() in ["guided", "gate"]:
                        self.mode = "guided"
                        console.print("[green]Switched mode to:[/green] 🛡️ Guided (human approvals)\n")
                    else:
                        console.print(f"[dim]Active: {self.mode}. Usage: /mode [auto|guided][/dim]\n")
                    continue

                elif user_input.startswith("/repo"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        self.repo_path = parts[1].strip()
                        console.print(f"[green]Workspace target updated to:[/green] {self.repo_path}\n")
                    else:
                        console.print(f"[dim]Active repo: {self.repo_path}. Usage: /repo <path>[/dim]\n")
                    continue

                elif user_input in ["/new", "/clear"]:
                    self.session = self._conversation_manager.create_session(
                        repository_path=self.repo_path,
                        model=self.model,
                        mode=self.mode,
                    )
                    console.print("[green]Fresh session started.[/green]\n")
                    continue

                elif user_input == "/history":
                    self.show_history()
                    continue

                elif user_input == "/diff":
                    self.show_diff()
                    continue

                # Execute natural language goal
                await self.execute_goal(user_input)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Interrupted. Type '/exit' to quit or enter a new goal.[/dim]\n")
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}\n")

    def show_help(self):
        table = Table(box=None, padding=(0, 2))
        table.add_column("Command", style="bold cyan")
        table.add_column("Description")
        table.add_row("<goal>", "State your goal in plain text (e.g. 'Add greeting test and run pytest')")
        table.add_row("/model [gemini|ollama]", "Switch between ⚡ Gemini Flash and 🦙 Ollama Local")
        table.add_row("/mode [auto|guided]", "Toggle Autonomous mode or Guided approval gates")
        table.add_row("/diff", "View git diff of modified files in active workspace")
        table.add_row("/history", "View session message history")
        table.add_row("/repo <path>", "Switch target workspace repository")
        table.add_row("/new", "Start a fresh session")
        table.add_row("/exit", "Exit ASTRA")
        console.print("\n[bold]ASTRA Commands:[/bold]")
        console.print(table)
        console.print()

    def show_history(self):
        console.print(f"\n[bold]Session History ({len(self.session.messages)} messages):[/bold]")
        for m in self.session.messages:
            role_style = "bold green" if m.role == "user" else "bold cyan"
            console.print(f"[{role_style}]{m.role.capitalize()}:[/{role_style}] {m.content}")
        console.print()

    def show_diff(self):
        if not self.session.workspace_path:
            console.print("\n[dim]No workspace changes recorded yet.[/dim]\n")
            return
        ws_p = Path(self.session.workspace_path)
        try:
            import subprocess
            res = subprocess.run(["git", "diff"], cwd=ws_p, capture_output=True, text=True)
            if res.stdout:
                console.print(Panel(res.stdout, title="Git Diff", border_style="green"))
            else:
                console.print("\n[dim]Working tree clean. No uncommitted diffs.[/dim]\n")
        except Exception as e:
            console.print(f"[dim]Could not read git diff: {e}[/dim]\n")


def main():
    parser = argparse.ArgumentParser(description="ASTRA 2.0 Autonomous Software Engineer CLI")
    parser.add_argument("goal", nargs="?", help="Direct goal to execute (optional)")
    parser.add_argument("--model", "-m", default=None, choices=["ollama", "gemini", "qwen", "cloud", "flash"], help="LLM provider: gemini or ollama")
    parser.add_argument("--mode", default="autonomous", choices=["autonomous", "guided"], help="Execution mode")
    parser.add_argument("--repo", "-r", default=None, help="Target repository path or Git URL")

    args = parser.parse_args()

    cli = AstraCLI(model=args.model, mode=args.mode, repo_path=args.repo)

    if args.goal:
        asyncio.run(cli.execute_goal(args.goal))
    else:
        asyncio.run(cli.run_repl())


if __name__ == "__main__":
    main()
