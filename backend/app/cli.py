from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.observability.logging import logger
from app.runtime.events import central_event_bus
from app.runtime.lifecycle import TaskLifecycleManager
from app.runtime.session import conversation_manager, AgentSession

console = Console()

BANNER = """[bold cyan]
    █████╗ ███████╗████████╗██████╗  █████╗ 
   ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗
   ███████║███████╗   ██║   ██████╔╝███████║
   ██╔══██║╚════██║   ██║   ██╔══██╗██╔══██║
   ██║  ██║███████║   ██║   ██║  ██║██║  ██║
   ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝
[/bold cyan][dim]2.0 — Autonomous Software Engineer (Terminal Edition)[/dim]
"""


class AstraCLI:
    def __init__(
        self,
        model: str = "ollama",
        mode: str = "autonomous",
        repo_path: Optional[str] = None,
    ):
        self.model = "ollama/qwen2.5-coder:3b" if "ollama" in model.lower() or "qwen" in model.lower() else "gemini/gemini-2.5-flash"
        self.mode = mode
        self.repo_path = repo_path or str(Path.cwd().resolve())
        self.lifecycle = TaskLifecycleManager()
        self.session: AgentSession = conversation_manager.create_session(
            repository_path=self.repo_path,
            model=self.model,
            mode=self.mode,
            initial_title="Terminal CLI Session",
        )

    def print_header(self):
        console.print(BANNER)
        model_display = "🦙 Ollama Local (qwen2.5-coder:3b)" if "ollama" in self.model else "⚡ Gemini Flash (gemini-2.5-flash)"
        repo_name = Path(self.repo_path).name or self.repo_path

        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="right")
        table.add_column(style="bold")
        table.add_row("Model:", model_display)
        table.add_row("Mode:", "🚀 Autonomous (auto-correct & push)" if self.mode == "autonomous" else "🛡️ Guided (human approvals)")
        table.add_row("Repository:", f"[cyan]{self.repo_path}[/cyan] ({repo_name})")
        table.add_row("Session ID:", f"[dim]{self.session.id}[/dim]")

        console.print(Panel(table, border_style="cyan", title="[bold]Agent Ready[/bold]", title_align="left"))
        console.print("[dim]Type your goal in plain language, or '/help' for commands, '/exit' to quit.\n[/dim]")

    async def execute_goal(self, goal: str) -> None:
        """Executes a goal through the autonomous agent loop and streams live terminal events."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        # Record user message in session
        conversation_manager.add_user_message(self.session.id, goal, task_id=task_id)

        # Build prompt incorporating previous session context
        contextual_goal = conversation_manager.build_contextual_prompt(self.session.id, goal)

        console.print(f"\n[bold green]You:[/bold green] {goal}")
        console.print(f"[dim]ASTRA dispatched task [bold]{task_id}[/bold]...[/dim]\n")

        # Register task in lifecycle manager
        task_info = self.lifecycle.create_task(
            task_id=task_id,
            goal=contextual_goal,
            repository_path=self.repo_path,
            model=self.model,
            mode=self.mode,
        )

        if self.session.workspace_path:
            task_info["workspace_path"] = self.session.workspace_path

        # Subscribe to real-time events
        event_queue = central_event_bus.subscribe(task_id)

        # Launch agent execution task
        agent_task = asyncio.create_task(self.lifecycle.run_task_async(task_id))

        last_phase = ""
        current_step = 0

        try:
            while not agent_task.done() or not event_queue.empty():
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue

                ev_type = str(event.event_type)
                msg = event.message
                payload = event.payload or {}

                if ev_type in ["PLANNING_STARTED", "PLANNING"]:
                    if last_phase != "plan":
                        console.print("[bold magenta]📋 Phase 1 — Architectural Investigation & Planning[/bold magenta]")
                        last_phase = "plan"

                elif ev_type in ["PLAN_GENERATED"]:
                    steps = payload.get("steps", [])
                    if steps:
                        console.print("  [dim]Planned Actions:[/dim]")
                        for idx, step in enumerate(steps, 1):
                            console.print(f"   [cyan]{idx}.[/cyan] {step}")

                elif ev_type in ["TOOL_CALL_STARTED"]:
                    if last_phase != "exec":
                        console.print("\n[bold sky_blue1]⚡ Phase 2 — Autonomous Execution[/bold sky_blue1]")
                        last_phase = "exec"
                    tool = payload.get("tool", "")
                    cmd = payload.get("command", "") or msg
                    console.print(f"  [yellow]→[/yellow] [dim]{tool}:[/dim] [bold]{cmd}[/bold]")

                elif ev_type in ["FILE_CHANGED"]:
                    path = payload.get("path", "")
                    op = payload.get("operation", "modified")
                    console.print(f"  [bold green]✓[/bold green] [green]{op.capitalize()}[/green] [bold cyan]{path}[/bold cyan]")

                elif ev_type in ["TEST_STARTED"]:
                    cmd = payload.get("command", "pytest")
                    console.print(f"\n[bold yellow]🧪 Running Tests:[/bold yellow] [dim]{cmd}[/dim]")

                elif ev_type in ["TEST_COMPLETED"]:
                    passed = payload.get("passed", 0)
                    failed = payload.get("failed", 0)
                    if failed > 0:
                        console.print(f"  [bold red]✗[/bold red] [red]{failed} tests failed[/red] ([green]{passed} passed[/green])")
                    else:
                        console.print(f"  [bold green]✓[/bold green] [green]All {passed} tests passed clean[/green]")

                elif ev_type in ["DEBUG_STARTED", "HYPOTHESIS_FORMULATED", "REPLAN_TRIGGERED"]:
                    if last_phase != "debug":
                        console.print("\n[bold orange3]🔁 Phase 3 — Self-Correction & Autonomous Replanning[/bold orange3]")
                        last_phase = "debug"
                    console.print(f"  [orange3]↳[/orange3] {msg}")

                elif ev_type in ["AUDIT_COMPLETED"]:
                    console.print(f"\n[bold cyan]🛡️ Phase 4 — Pre-Commit Audit:[/bold cyan] [dim]{msg}[/dim]")

                elif ev_type in ["COMMIT_CREATED"]:
                    sha = payload.get("sha", "")[:7]
                    console.print(f"  [bold green]📦 Git Commit:[/bold green] [cyan]{sha}[/cyan] • {msg}")

                elif ev_type in ["PUSH_COMPLETED", "PR_CREATED"]:
                    console.print(f"  [bold blue]🚀 Git Delivery:[/bold blue] {msg}")

                elif ev_type in ["APPROVAL_REQUIRED"]:
                    console.print(Panel(
                        f"[bold yellow]HUMAN AUTHORIZATION REQUIRED[/bold yellow]\n\n{msg}",
                        border_style="yellow"
                    ))
                    choice = input("  Authorize execution? [y/N]: ").strip().lower()
                    if choice in ["y", "yes"]:
                        await self.lifecycle.resume_task_after_approval(task_id, approved=True)
                    else:
                        await self.lifecycle.resume_task_after_approval(task_id, approved=False)

                elif ev_type in ["TASK_COMPLETED"]:
                    console.print(f"\n[bold green]✓ Task Finished Successfully[/bold green]\n")

                elif ev_type in ["TASK_FAILED"]:
                    console.print(f"\n[bold red]✗ Task Failed[/bold red]: {msg}\n")

                elif ev_type in ["ERROR"]:
                    console.print(f"  [red]Error: {msg}[/red]")

            # Await agent completion
            await agent_task

        except asyncio.CancelledError:
            self.lifecycle.cancel_task(task_id)
            console.print("[yellow]Agent task cancelled by user.[/yellow]")
        finally:
            central_event_bus.unsubscribe(task_id, event_queue)

        # Update session workspace if newly created
        task_data = self.lifecycle.get_task(task_id)
        if task_data and task_data.get("workspace_path"):
            self.session.workspace_path = task_data["workspace_path"]

        # Display Final Summary Card
        report = (task_data or {}).get("final_report") or {}
        evidence = report.get("evidence") or {}
        tests = evidence.get("tests") or {}
        files = evidence.get("files_changed") or []

        summary_table = Table(title="ASTRA Execution Report", border_style="cyan", show_header=True)
        summary_table.add_column("Metric", style="dim")
        summary_table.add_column("Result", style="bold")

        status_str = task_data.get("verification_status", "uncertain").upper()
        summary_table.add_row("Status", f"[green]{status_str}[/green]" if "VERIF" in status_str else f"[red]{status_str}[/red]")
        summary_table.add_row("Tests Passed", str(tests.get("passed", 0)))
        summary_table.add_row("Tests Failed", str(tests.get("failed", 0)))
        summary_table.add_row("Files Modified", f"{len(files)} files ({', '.join(files[:3]) if files else 'none'})")

        if report.get("commit"):
            summary_table.add_row("Commit", f"{report['commit'].get('commit_sha', '')[:7]}")

        console.print(summary_table)
        console.print()

    async def run_repl(self) -> None:
        """Interactive Read-Eval-Print Loop (terminal chat mode)."""
        self.print_header()

        while True:
            try:
                prompt_text = "[bold cyan]astra > [/bold cyan]"
                console.print(prompt_text, end="")
                user_input = input().strip()

                if not user_input:
                    continue

                # Built-in Slash Commands
                if user_input in ["/exit", "/quit", "exit", "quit"]:
                    console.print("[dim]Exiting ASTRA. Bye![/dim]")
                    break

                elif user_input == "/help":
                    self.show_help()
                    continue

                elif user_input.startswith("/model"):
                    parts = user_input.split()
                    if len(parts) > 1 and parts[1].lower() in ["ollama", "qwen", "local"]:
                        self.model = "ollama/qwen2.5-coder:3b"
                        console.print("[green]Switched model to:[/green] 🦙 Ollama Local (qwen2.5-coder:3b)")
                    elif len(parts) > 1 and parts[1].lower() in ["gemini", "cloud"]:
                        self.model = "gemini/gemini-2.5-flash"
                        console.print("[green]Switched model to:[/green] ⚡ Gemini Flash (gemini-2.5-flash)")
                    else:
                        console.print(f"[dim]Current model: {self.model}. Use: /model [ollama|gemini][/dim]")
                    continue

                elif user_input.startswith("/mode"):
                    parts = user_input.split()
                    if len(parts) > 1 and parts[1].lower() in ["auto", "autonomous"]:
                        self.mode = "autonomous"
                        console.print("[green]Switched mode to:[/green] 🚀 Autonomous")
                    elif len(parts) > 1 and parts[1].lower() in ["guided", "gate"]:
                        self.mode = "guided"
                        console.print("[green]Switched mode to:[/green] 🛡️ Guided Gate")
                    else:
                        console.print(f"[dim]Current mode: {self.mode}. Use: /mode [auto|guided][/dim]")
                    continue

                elif user_input.startswith("/repo"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        new_repo = parts[1].strip()
                        self.repo_path = new_repo
                        console.print(f"[green]Target repository updated to:[/green] {new_repo}")
                    else:
                        console.print(f"[dim]Current repository: {self.repo_path}. Use: /repo <path-or-url>[/dim]")
                    continue

                elif user_input in ["/new", "/clear"]:
                    self.session = conversation_manager.create_session(
                        repository_path=self.repo_path,
                        model=self.model,
                        mode=self.mode,
                    )
                    console.print("[green]Started a new conversational session.[/green]")
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
                console.print("\n[dim]Session interrupted. Type '/exit' to quit or enter a new goal.[/dim]")
            except Exception as e:
                console.print(f"[bold red]Unexpected error:[/bold red] {e}")

    def show_help(self):
        table = Table(title="ASTRA Terminal Commands", border_style="cyan")
        table.add_column("Command", style="bold cyan")
        table.add_column("Description")
        table.add_row("<goal>", "Tell ASTRA what to build, investigate, fix, or test in plain English")
        table.add_row("/model [ollama|gemini]", "Switch between 🦙 Ollama Local and ⚡ Gemini Flash")
        table.add_row("/mode [auto|guided]", "Toggle Autonomous or Guided approval gates")
        table.add_row("/repo <path-or-url>", "Switch target repository or working directory")
        table.add_row("/diff", "View git diff of modified files in the active workspace")
        table.add_row("/history", "View message history and previous turns in this session")
        table.add_row("/new", "Start a fresh session with cleared context")
        table.add_row("/exit", "Exit the CLI")
        console.print(table)

    def show_history(self):
        console.print(f"[bold]Session History ({len(self.session.messages)} messages):[/bold]")
        for m in self.session.messages:
            role_style = "bold green" if m.role == "user" else "bold cyan"
            console.print(f"[{role_style}]{m.role.capitalize()}:[/{role_style}] {m.content}")
            if m.files_changed:
                console.print(f"  [dim]Files: {', '.join(m.files_changed)}[/dim]")

    def show_diff(self):
        if not self.session.workspace_path:
            console.print("[dim]No active workspace recorded yet.[/dim]")
            return
        ws_p = Path(self.session.workspace_path)
        try:
            import subprocess
            res = subprocess.run(["git", "diff"], cwd=ws_p, capture_output=True, text=True)
            if res.stdout:
                console.print(Panel(res.stdout, title="Active Git Diff", border_style="green"))
            else:
                console.print("[dim]Working directory clean. No uncommitted diffs.[/dim]")
        except Exception as e:
            console.print(f"[dim]Could not read git diff: {e}[/dim]")


def main():
    parser = argparse.ArgumentParser(description="ASTRA 2.0 Autonomous Software Engineer CLI")
    parser.add_argument("goal", nargs="?", help="Direct goal or instruction to execute (optional)")
    parser.add_argument("--model", "-m", default="ollama", choices=["ollama", "gemini", "qwen", "cloud"], help="LLM provider: ollama or gemini")
    parser.add_argument("--mode", default="autonomous", choices=["autonomous", "guided"], help="Execution mode")
    parser.add_argument("--repo", "-r", default=None, help="Target repository path or Git URL")

    args = parser.parse_args()

    cli = AstraCLI(model=args.model, mode=args.mode, repo_path=args.repo)

    if args.goal:
        # Single-shot execution mode
        asyncio.run(cli.execute_goal(args.goal))
    else:
        # Interactive REPL mode
        asyncio.run(cli.run_repl())


if __name__ == "__main__":
    main()
