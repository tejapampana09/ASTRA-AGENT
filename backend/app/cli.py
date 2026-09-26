from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import uuid
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load local environment variables (.env)
load_dotenv()

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
    "what can you do": "🛠️ **What I can do:**\n- 🔍 Investigate codebase architecture & dependencies\n- 📝 Plan multi-step modifications\n- 💻 Edit and create files in your repository\n- 🧪 Run test suites (pytest/unittest) and observe real test output\n- 🔁 Autonomously debug and replan if tests fail\n- 📦 Create conventional git commits and prepare pull requests",
    "what can you do?": "🛠️ **What I can do:**\n- 🔍 Investigate codebase architecture & dependencies\n- 📝 Plan multi-step modifications\n- 💻 Edit and create files in your repository\n- 🧪 Run test suites (pytest/unittest) and observe real test output\n- 🔁 Autonomously debug and replan if tests fail\n- 📦 Create conventional git commits and prepare pull requests",
}


def get_conversational_response(prompt: str) -> Optional[str]:
    """Detects purely conversational or chit-chat queries to prevent spinning up full tasks."""
    raw = prompt.strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", raw).strip()

    if raw in CONVERSATIONAL_PROMPTS:
        return CONVERSATIONAL_PROMPTS[raw]
    if cleaned in CONVERSATIONAL_PROMPTS:
        return CONVERSATIONAL_PROMPTS[cleaned]

    # Greetings
    if cleaned in ["yo", "sup", "howdy", "hola", "heya", "greetings"]:
        return "👋 Hey! Ready to work on your code. What would you like to build, inspect, or test?"

    # Status / casual queries ("whats going on", "what's up", "how are you")
    if cleaned in [
        "whats going on", "whts going on", "what is going on",
        "whats up", "what is up", "wassup",
        "how are you", "how are u", "how r u",
        "how is it going", "hows it going", "hows everything",
        "what are you doing", "what r u doing"
    ]:
        return "👋 Everything is running smoothly! I'm standing by to write code, fix bugs, or run tests in this workspace. What shall we work on?"

    # Gratitude
    if cleaned in ["thanks", "thank you", "thx", "ty", "cool", "great", "awesome", "perfect"]:
        return "You're welcome! Let me know whenever you'd like to work on the next task."

    # Identity
    if cleaned in ["who are u", "what are you", "who made you"]:
        return CONVERSATIONAL_PROMPTS["who are you"]

    return None


BANNER = """
    █████╗ ███████╗████████╗██████╗  █████╗ 
   ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗
   ███████║███████╗   ██║   ██████╔╝███████║
   ██╔══██║╚════██║   ██║   ██╔══██╗██╔══██║
   ██║  ██║███████║   ██║   ██║  ██║██║  ██║
   ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝

2.0 — Autonomous Software Engineer (Terminal Edition)
"""


class AstraCLI:
    def __init__(
        self,
        model: Optional[str] = None,
        mode: str = "autonomous",
        repo_path: Optional[str] = None,
    ):
        from app.llm.resolver import resolve_model
        resolved = resolve_model(requested_model=model)
        self.model = resolved.model

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
        console.print(BANNER)
        model_str = (self.model or "").lower()
        if "gemini" in model_str:
            model_display = "⚡ Gemini 3.8 Flash (gemini-3.8-flash)"
        elif "claude" in model_str or "anthropic" in model_str:
            model_display = "🧠 Anthropic Claude (claude-3-7-sonnet)"
        elif "gpt" in model_str or "openai" in model_str:
            model_display = "🤖 OpenAI (gpt-4o)"
        elif "qwen" in model_str or "ollama" in model_str:
            model_display = "🦙 Ollama Local (qwen2.5-coder:3b)"
        else:
            model_display = f"🤖 {self.model}"

        if self.mode == "guided":
            mode_display = "🛡️ Guided (human approvals)"
        else:
            mode_display = "🚀 Autonomous (auto-correct & push)"

        console.print(f"Model:      {model_display}")
        console.print(f"Mode:       {mode_display}")
        console.print(f"Repository: {self.repo_path}\n")

    async def execute_goal(self, goal: str) -> None:
        """Executes a goal cleanly with live terminal activity indicators."""
        # Check for simple conversational messages first
        conv_reply = get_conversational_response(goal)
        if conv_reply:
            console.print(f"\n[bold green]ASTRA:[/bold green] {conv_reply}\n")
            return

        silence_background_logging()
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        self._conversation_manager.add_user_message(self.session.id, goal, task_id=task_id)
        contextual_goal = self._conversation_manager.build_contextual_prompt(self.session.id, goal)

        console.print(f"\n[bold green]You:[/bold green] {goal}")
        console.print(f"[dim]● Task [bold]{task_id}[/bold] initiated[/dim]\n")

        task_info = self.lifecycle.create_task(
            task_id=task_id,
            goal=contextual_goal,
            repository_path=self.repo_path,
            model=self.model,
            mode=self.mode,
        )

        task_info["execution_mode"] = "LOCAL"

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

                    if ev_type in ["UNDERSTAND", "PLANNING"]:
                        status.update("[cyan]Analyzing repository architecture...[/cyan]")

                    elif ev_type in ["PLANNING_STARTED"]:
                        status.stop()
                        console.print("  [bold green]✓[/bold green] Repository analyzed")
                        status.start()

                    elif ev_type in ["PLAN_GENERATED"]:
                        status.stop()
                        steps = payload.get("steps", [])
                        console.print("  [bold green]✓[/bold green] Plan generated\n")
                        for idx, step in enumerate(steps, 1):
                            console.print(f"    [dim]{idx}.[/dim] {step}")
                        console.print()
                        status.start()
                        status.update("[cyan]Executing planned actions...[/cyan]")

                    elif ev_type in ["TOOL_CALL_STARTED"]:
                        status.stop()
                        tool = payload.get("tool", "")
                        cmd = payload.get("command", "") or msg
                        path = payload.get("path", "")
                        if "read" in tool.lower() or "view" in str(cmd).lower():
                            console.print(f"  [cyan]→[/cyan] Reading [bold]{path or cmd}[/bold]")
                        elif "edit" in tool.lower() or "create" in tool.lower() or "file" in tool.lower():
                            console.print(f"  [green]→[/green] Editing [bold]{path or cmd}[/bold]")
                        else:
                            cmd_disp = cmd.replace("\n", " ").strip()
                            if len(cmd_disp) > 70:
                                cmd_disp = cmd_disp[:67] + "..."
                            console.print(f"  [yellow]→[/yellow] Running [bold]{cmd_disp}[/bold]")
                        status.start()

                    elif ev_type in ["TEST_STARTED"]:
                        status.stop()
                        cmd = payload.get("command", "pytest")
                        console.print(f"  [yellow]→[/yellow] Running [bold]{cmd}[/bold]")
                        status.start()

                    elif ev_type in ["TEST_COMPLETED"]:
                        status.stop()
                        passed = payload.get("passed", 0)
                        failed = payload.get("failed", 0)
                        if failed > 0:
                            console.print(f"  [bold red]✗[/bold red] [red]{failed} tests failed[/red]")
                        else:
                            console.print(f"  [bold green]✓[/bold green] [green]{passed} tests passed[/green]")
                        status.start()

                    elif ev_type in ["DEBUG_STARTED", "HYPOTHESIS_FORMULATED"]:
                        status.stop()
                        console.print("  [orange3]→[/orange3] Diagnosing failure")
                        status.start()

                    elif ev_type in ["REPLAN_TRIGGERED"]:
                        status.stop()
                        console.print("  [orange3]→[/orange3] Fixing code & reapplying plan")
                        status.start()

                    elif ev_type in ["AUDIT_COMPLETED", "DIFF_INSPECTED"]:
                        status.stop()
                        console.print("  [bold green]✓[/bold green] Diff verified")
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
                        console.print("\n[bold green]Task completed.[/bold green]\n")
                        status.start()

                    elif ev_type in ["TASK_FAILED"]:
                        status.stop()
                        console.print(f"\n[bold red]Task incomplete:[/bold red] {msg}\n")
                        status.start()

                await agent_task

            except asyncio.CancelledError:
                self.lifecycle.cancel_task(task_id)
                console.print("\n[yellow]Task cancelled.[/yellow]\n")
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
                console.print("astra > ", end="")
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
                    if len(parts) > 1:
                        from app.llm.resolver import resolve_model
                        resolved = resolve_model(requested_model=parts[1].lower())
                        self.model = resolved.model
                        console.print(f"[green]Switched model to:[/green] {self.model}\n")
                    else:
                        console.print(f"[dim]Active: {self.model}. Usage: /model [ollama|gemini][/dim]\n")
                    continue

                elif user_input.startswith("/mode"):
                    parts = user_input.split()
                    if len(parts) > 1 and parts[1].lower() in ["guided", "gate"]:
                        self.mode = "guided"
                        console.print("[green]Switched mode to:[/green] 🛡️ Guided (human approvals)\n")
                    else:
                        self.mode = "autonomous"
                        console.print("[green]Switched mode to:[/green] 🚀 Autonomous\n")
                    continue

                elif user_input.startswith("/repo"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        raw_target = parts[1].strip().strip('"\'')
                        target_dir = Path(raw_target).resolve()
                        if not target_dir.exists():
                            console.print(f"[bold red]Error:[/bold red] Target directory does not exist: {target_dir}\n")
                            continue
                        if not target_dir.is_dir():
                            console.print(f"[bold red]Error:[/bold red] Target path is not a directory: {target_dir}\n")
                            continue

                        # Completely reset repository and session context
                        # 1. Clear previous repository RAG context & vector store chunks
                        try:
                            from app.rag.vector_store import get_vector_store
                            vs = get_vector_store()
                            old_repo_name = Path(self.repo_path).name or "default_repo"
                            vs.delete_repo_chunks(old_repo_name)
                            vs.delete_repo_chunks(str(Path(self.repo_path).resolve()))
                        except Exception as e:
                            logger.debug(f"Failed to clear old vector chunks: {e}")

                        # 2. Update active repository path and recreate session object
                        self.repo_path = str(target_dir)
                        new_repo_name = target_dir.name or "default_repo"
                        self.session = self._conversation_manager.create_session(
                            repository_path=self.repo_path,
                            model=self.model,
                            mode=self.mode,
                            initial_title=f"Session for {target_dir.name}",
                        )
                        self.session.workspace_path = str(target_dir)

                        # 3. Explicitly build and load fresh repository index for new target
                        try:
                            from app.rag.indexer import RepositorySemanticIndexer
                            from app.rag.vector_store import get_vector_store
                            vs = get_vector_store()
                            new_chunks = RepositorySemanticIndexer.index_repository(target_dir, repo_id=new_repo_name)
                            vs.upsert_chunks(new_chunks)
                        except Exception as e:
                            logger.debug(f"Failed to load new repo index: {e}")

                        self.print_header()
                    else:
                        console.print(f"[dim]Active repository: {self.repo_path}. Usage: /repo <path>[/dim]\n")
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

                # Execute natural language goal via LangGraph + OpenHands directly on target repository
                await self.execute_goal(user_input)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Interrupted. Type '/exit' to quit or enter a new goal.[/dim]\n")
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}\n")

    def show_help(self):
        table = Table(box=None, padding=(0, 2))
        table.add_column("Command", style="bold cyan")
        table.add_column("Description")
        table.add_row("<goal>", "State your goal in plain text (e.g. 'Fix the failing tests in this repository')")
        table.add_row("/repo <path>", "Switch target workspace repository (completely resets context)")
        table.add_row("/model [ollama|gemini]", "Switch between 🦙 Ollama Local and ⚡ Gemini Flash")
        table.add_row("/mode [auto|guided]", "Toggle Autonomous mode or Guided approval gates")
        table.add_row("/diff", "View git diff of modified files in active repository")
        table.add_row("/history", "View session message history")
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
        target = self.session.workspace_path or self.repo_path
        if not target:
            console.print("\n[dim]No repository path selected.[/dim]\n")
            return
        ws_p = Path(target)
        try:
            import subprocess
            subprocess.run(["git", "add", "-N", "."], cwd=ws_p, capture_output=True, check=False)
            res = subprocess.run(["git", "diff", "HEAD"], cwd=ws_p, capture_output=True, text=True, check=False)
            diff_text = res.stdout
            if not diff_text.strip():
                res2 = subprocess.run(["git", "diff"], cwd=ws_p, capture_output=True, text=True, check=False)
                diff_text = res2.stdout
            if diff_text.strip():
                console.print(Panel(diff_text, title="Git Diff", border_style="green"))
            else:
                console.print("\n[dim]Working tree clean. No uncommitted diffs.[/dim]\n")
        except Exception as e:
            console.print(f"[dim]Could not read git diff: {e}[/dim]\n")


def main():
    try:
        parser = argparse.ArgumentParser(description="ASTRA 2.0 Autonomous Software Engineer CLI")
        parser.add_argument("goal", nargs="?", help="Direct goal to execute (optional)")
        parser.add_argument("--model", "-m", default=None, help="LLM model or provider (e.g. ollama, gemini, qwen2.5-coder:3b)")
        parser.add_argument("--mode", default="autonomous", choices=["autonomous", "guided"], help="Execution mode")
        parser.add_argument("--repo", "-r", default=None, help="Target repository path or Git URL")

        args = parser.parse_args()

        cli = AstraCLI(model=args.model, mode=args.mode, repo_path=args.repo)

        if args.goal:
            asyncio.run(cli.execute_goal(args.goal))
        else:
            asyncio.run(cli.run_repl())
    except KeyboardInterrupt:
        console.print("\n[dim]✦ Exiting ASTRA. Bye![/dim]\n")
        sys.exit(0)
    except SystemExit:
        pass


if __name__ == "__main__":
    main()
