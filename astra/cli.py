"""ASTRA 3.0 Next-Gen Terminal Interface.

Instant startup, live execution streaming, rich git and workspace tools.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from astra import __version__
from astra.agent import AgentCallback, AstraAgent
from astra.config import settings
from astra.tools import ToolExecutor

console = Console()

BANNER_ART = f"""[bold cyan]    █████╗ ███████╗████████╗██████╗  █████╗ [/bold cyan]
[bold cyan]   ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗[/bold cyan]
[bold cyan]   ███████║███████╗   ██║   ██████╔╝███████║[/bold cyan]
[bold cyan]   ██╔══██║╚════██║   ██║   ██╔══██╗██╔══██║[/bold cyan]
[bold cyan]   ██║  ██║███████║   ██║   ██║  ██║██║  ██║[/bold cyan]
[bold cyan]   ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝[/bold cyan]
[dim]v{__version__} — Autonomous Software Engineering Agent[/dim]"""


def get_model_badge(model_name: Optional[str]) -> str:
    m = (model_name or "").lower()
    if "teja" in m or "colab" in m:
        return "[bold red]🔥 TejaAI Gemma-4[/bold red] [dim](Cloud GPU)[/dim]"
    elif "groq" in m or "llama" in m:
        return "[bold green]⚡ Groq Llama 3.3 70B[/bold green] [dim](14.4k req/day)[/dim]"
    elif "openrouter" in m:
        return "[bold cyan]🌐 OpenRouter[/bold cyan]"
    elif "lite" in m:
        return "[bold blue]⚡ Google Gemini[/bold blue] [dim](3.5 Flash-Lite)[/dim]"
    elif "gemini" in m:
        return "[bold blue]⚡ Google Gemini[/bold blue] [dim](3.5 Flash)[/dim]"
    elif "claude" in m or "anthropic" in m:
        return "[bold magenta]🧠 Anthropic Claude[/bold magenta]"
    elif "gpt" in m or "openai" in m:
        return "[bold green]🤖 OpenAI GPT-4o[/bold green]"
    elif "ollama" in m or "qwen" in m:
        return "[bold yellow]🦙 Ollama Local[/bold yellow]"
    return f"[cyan]{model_name}[/cyan]"


class TerminalCallback(AgentCallback):
    """Prints agent actions and thoughts live with stylish formatting."""

    def on_phase_change(self, phase: str, details: str = "") -> None:
        if phase == "VERIFY":
            console.print(f"  [bold magenta]🔍 Verifying:[/bold magenta] [white]{details}[/white]")
        elif phase == "FIX":
            console.print(f"  [bold red]🩹 Self-Healing:[/bold red] [yellow]{details}[/yellow]")
        elif phase == "DONE":
            console.print(f"  [bold green]✓ Phase Complete:[/bold green] [dim]{details}[/dim]")

    def on_thought(self, thought: str) -> None:
        md = Markdown(thought, code_theme="monokai")
        console.print(Panel(md, title="[bold cyan]🧠 Reasoning[/bold cyan]", border_style="dim cyan", padding=(0, 2)))

    def on_tool_call(self, name: str, args: Dict[str, Any]) -> None:
        args_preview = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
        console.print(f"  [bold yellow]⚙️ Executing:[/bold yellow] [bold]{name}[/bold] [dim]({args_preview})[/dim]")

    def on_tool_result(self, name: str, result: str, duration_ms: float = 0.0, exit_code: Optional[int] = None) -> None:
        lines = result.strip().splitlines()
        preview = lines[0] if lines else ""
        if len(lines) > 1:
            preview += f" [dim](+{len(lines)-1} more lines)[/dim]"

        meta_parts = []
        if duration_ms > 0:
            meta_parts.append(f"⚡ {duration_ms:.0f}ms")
        if exit_code is not None:
            meta_parts.append(f"exit {exit_code}")
        meta_str = f" [dim cyan]({ ' • '.join(meta_parts) })[/dim cyan]" if meta_parts else ""

        console.print(f"  [dim]↳ Result: {preview[:100]}[/dim]{meta_str}")

    def on_state_change(self, state: Any, details: str = "") -> None:
        pass

    def on_file_changed(self, file_path: str, action: str = "modified", diff: str = "") -> None:
        tag = "Created" if action == "created" else ("Deleted" if action == "deleted" else "Modified")
        console.print(f"  [bold green]📝 {tag} File:[/bold green] [cyan]{file_path}[/cyan]")
        if diff and diff.strip():
            syntax = Syntax(diff.strip(), "diff", theme="monokai", line_numbers=True)
            console.print(
                Panel(
                    syntax,
                    title=f"[bold green]🔍 Unified Patch Preview: {file_path}[/bold green]",
                    subtitle="[dim]Antigravity Color Diff[/dim]",
                    border_style="green",
                    padding=(0, 1),
                )
            )

    def on_verification(self, passed: bool, summary: str, details: str = "") -> None:
        if passed:
            console.print(f"  [bold green]✅ Independent Verification Passed:[/bold green] [dim]{summary}[/dim]")
        else:
            console.print(f"  [bold red]❌ Independent Verification Failed:[/bold red] [yellow]{summary}[/yellow]")

    def on_plan_updated(self, steps: Any) -> None:
        if not steps:
            return
        table = Table(box=None, show_header=False, padding=(0, 1))
        table.add_column("Icon", width=5)
        table.add_column("Step")
        for s in steps:
            title = getattr(s, "title", "") or (s.get("title") if isinstance(s, dict) else str(s))
            raw_st = getattr(s, "status", "") or (s.get("status") if isinstance(s, dict) else "")
            st = str(raw_st.value if hasattr(raw_st, "value") else raw_st).upper()
            if "COMPLETED" in st:
                table.add_row("[bold green][✓][/bold green]", f"[green]{title}[/green]")
            elif "IN_PROGRESS" in st:
                table.add_row("[bold cyan][▶][/bold cyan]", f"[bold cyan]{title}[/bold cyan] [dim](in progress)[/dim]")
            elif "FAILED" in st:
                table.add_row("[bold red][✗][/bold red]", f"[red]{title}[/red]")
            else:
                table.add_row("[dim][ ][/dim]", f"[dim]{title}[/dim]")

        console.print(Panel(
            table,
            title="[bold cyan]📋 ASTRA Dynamic Execution Plan[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))


class AstraCLI:
    def __init__(
        self,
        workspace_path: Optional[str] = None,
        model: Optional[str] = None,
        ask_commands: bool = True,
    ):
        self.workspace_path = Path(workspace_path or settings.workspace_path).resolve()
        self.model = model or settings.default_model
        self.tools = ToolExecutor(self.workspace_path)
        self.ask_commands = ask_commands
        self.active_status = None

    def cli_approval_handler(self, tool_name: str, description: str, args: Dict[str, Any]) -> Any:
        """Interactive Antigravity-style command approval guard and question prompter."""
        if tool_name == "ask_question":
            question = args.get("question", "")
            options = args.get("options") or []
            if self.active_status:
                try:
                    self.active_status.stop()
                except Exception:
                    pass

            table = Table(box=None, show_header=False, padding=(0, 2))
            table.add_column("Num", style="bold green", width=6)
            table.add_column("Option", style="bold white")
            if options:
                for idx, opt in enumerate(options, 1):
                    rec = " [bold green](Recommended)[/bold green]" if idx == 1 and not opt.startswith("(") else ""
                    table.add_row(f"[{idx}]", f"{opt}{rec}")

            console.print()
            content_items = [Text(question, style="bold cyan")]
            if options:
                content_items.append(Text(""))
                content_items.append(table)

            console.print(
                Panel(
                    Group(*content_items),
                    title="[bold yellow]❓ ASTRA Interactive Question[/bold yellow]",
                    subtitle="[dim]Antigravity Multi-Choice Selector[/dim]",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )

            try:
                if options:
                    ans = console.input(f"[bold cyan]Select option [1-{len(options)}] or write response: [/bold cyan]").strip()
                    if ans.isdigit() and 1 <= int(ans) <= len(options):
                        chosen = options[int(ans) - 1]
                    elif not ans:
                        chosen = options[0]
                    else:
                        chosen = ans
                else:
                    ans = console.input("[bold cyan]Your response: [/bold cyan]").strip()
                    chosen = ans or "(Accepted default)"

                console.print(f"[green]✓ Selected:[/green] [white]{chosen}[/white]\n")
                if self.active_status:
                    try:
                        self.active_status.start()
                    except Exception:
                        pass
                return chosen
            except (KeyboardInterrupt, EOFError):
                if self.active_status:
                    try:
                        self.active_status.start()
                    except Exception:
                        pass
                return options[0] if options else "(Cancelled)"

        if tool_name == "run_command":
            if not self.ask_commands:
                return True

            cmd = args.get("command", "")
            if self.active_status:
                try:
                    self.active_status.stop()
                except Exception:
                    pass

            console.print()
            console.print(
                Panel(
                    f"[bold yellow]$[/bold yellow] [bold white]{cmd}[/bold white]",
                    title="[bold yellow]🛡️ ASTRA Shell Command Confirmation[/bold yellow]",
                    subtitle="[dim]Antigravity Security Guard[/dim]",
                    border_style="yellow",
                    padding=(0, 2),
                )
            )
            try:
                choice = console.input("[bold cyan]Execute this command? [Y/n/always/quit]: [/bold cyan]").strip().lower()
                if choice in ("a", "always"):
                    self.ask_commands = False
                    console.print("[dim]✓ Auto-approve enabled for remaining commands in this run.[/dim]\n")
                    if self.active_status:
                        try:
                            self.active_status.start()
                        except Exception:
                            pass
                    return True
                if choice in ("q", "quit", "exit"):
                    console.print("\n[red]✗ Task cancelled by user.[/red]\n")
                    raise KeyboardInterrupt("Cancelled by user")

                approved = choice in ("", "y", "yes")
                if not approved:
                    console.print("[red]✗ Command rejected by user.[/red]\n")
                if self.active_status:
                    try:
                        self.active_status.start()
                    except Exception:
                        pass
                return approved
            except (KeyboardInterrupt, EOFError):
                console.print("\n[red]✗ Command rejected by user.[/red]\n")
                if self.active_status:
                    try:
                        self.active_status.start()
                    except Exception:
                        pass
                return False

        elif tool_name in ("write_file", "edit_file", "create_file", "delete_file"):
            if not self.ask_commands:
                return True
            fp = args.get("file_path", "")
            if self.active_status:
                try:
                    self.active_status.stop()
                except Exception:
                    pass
            console.print()
            try:
                choice = console.input(f"[bold yellow]Allow {tool_name} on '{fp}'? [Y/n/always]: [/bold yellow]").strip().lower()
                if choice in ("a", "always"):
                    self.ask_commands = False
                    if self.active_status:
                        try:
                            self.active_status.start()
                        except Exception:
                            pass
                    return True
                approved = choice in ("", "y", "yes")
                if self.active_status:
                    try:
                        self.active_status.start()
                    except Exception:
                        pass
                return approved
            except (KeyboardInterrupt, EOFError):
                if self.active_status:
                    try:
                        self.active_status.start()
                    except Exception:
                        pass
                return False
        return True

    def print_banner(self) -> None:
        console.print(BANNER_ART)
        console.print()

        git_status = self.tools.git_status()
        git_summary = git_status.splitlines()[0] if git_status else "No git repository"

        table = Table(box=None, show_header=False, padding=(0, 1))
        table.add_column("Key", style="bold white", width=12)
        table.add_column("Value")
        table.add_row("Model:", get_model_badge(self.model))
        table.add_row("Workspace:", f"[dim]{self.workspace_path}[/dim]")
        table.add_row("Git:", f"[cyan]{git_summary}[/cyan]")
        confirm_badge = "[bold green]ON (Ask before run)[/bold green]" if self.ask_commands else "[dim]OFF (Auto-run)[/dim]"
        table.add_row("Confirm:", confirm_badge)

        console.print(Panel(table, border_style="cyan", title="[bold]ASTRA Status[/bold]", title_align="left"))
        console.print("[dim]Type your goal in plain English, or [bold cyan]/help[/bold cyan] for commands.[/dim]\n")

    def show_help(self) -> None:
        table = Table(title="ASTRA Commands Reference", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="bold green", width=20)
        table.add_column("Description")

        table.add_row("<your goal>", "Execute any coding task (e.g. 'Fix login test in test_auth.py')")
        table.add_row("/ask, /confirm", "Toggle interactive command confirmation (Antigravity mode)")
        table.add_row("/model [name]", "Switch or view LLM (e.g. 'groq', 'gemini', 'teja-gemma', 'ollama')")
        table.add_row("/status, /git", "Check git status and modified files in workspace")
        table.add_row("/diff", "Show colorized git diff of changes")
        table.add_row("/files, /ls", "List files in the active workspace")
        table.add_row("/search <query>", "Search the live web (DuckDuckGo + Wikipedia, 100% free)")
        table.add_row("/repo <path>", "Switch target workspace directory")
        table.add_row("/run <cmd>, !<cmd>", "Run a shell command directly in the workspace")
        table.add_row("/clear, /cls", "Clear terminal screen and reprint banner")
        table.add_row("/exit, /quit", "Exit ASTRA")

        console.print(table)
        console.print()

    def show_status(self) -> None:
        status_text = self.tools.git_status()
        console.print(Panel(status_text, title="[bold]Git Status[/bold]", border_style="magenta"))
        console.print()

    def show_diff(self) -> None:
        diff_text = self.tools.git_diff()
        if not diff_text or diff_text == "No changes detected.":
            console.print("[green]✓ Working tree clean. No uncommitted changes.[/green]\n")
            return
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="[bold]Git Diff[/bold]", border_style="cyan"))
        console.print()

    def execute_goal(self, goal: str) -> None:
        goal = (goal or "").strip()
        if not goal:
            return

        if goal.lower().strip() in ("hey", "hi", "hello", "yo", "sup", "hey astra", "hi astra", "hello astra"):
            console.print()
            console.print(
                Panel(
                    "👋 [bold green]Hey there![/bold green] I am ASTRA, powered by your fine-tuned Gemma model.\n"
                    "I am ready to write code, implement algorithms, or solve bugs in your workspace.\n\n"
                    "[dim]Try running:\n"
                    "  python astra.py \"write a python function to reverse a string\"\n"
                    "  python astra.py \"create a fast binary search algorithm in python\"[/dim]",
                    title="[bold cyan]ASTRA Assistant[/bold cyan]",
                    border_style="cyan",
                    padding=(1, 2),
                )
            )
            console.print()
            return

        # Direct shell command auto-execution (e.g. 'git push', 'git status', 'pytest')
        first_word = goal.split()[0].lower() if goal.split() else ""
        if first_word in ("git", "pip", "pytest", "npm", "docker", "cargo", "dir", "ls") and not any(w in goal.lower() for w in ["write", "create", "how", "why", "what", "explain", "implement", "build"]):
            console.print()
            console.print(f"[bold cyan]$[/bold cyan] [bold]{goal}[/bold]")
            res = self.tools.run_command(goal)
            if res.strip():
                console.print(res)
            console.print()
            return

        console.print()
        console.print(
            Panel(
                f"[bold white]{goal}[/bold white]\n[dim]Workspace: {self.workspace_path} • Model: {self.model}[/dim]",
                title="[bold cyan]🚀 ASTRA Task Started[/bold cyan]",
                border_style="cyan",
            )
        )

        callback = TerminalCallback()
        agent = AstraAgent(
            workspace_path=self.workspace_path,
            model_name=self.model,
            max_iterations=15,
            callback=callback,
            approval_handler=self.cli_approval_handler,
        )

        status_spinner = console.status("[bold cyan]ASTRA is working autonomously...[/bold cyan]", spinner="dots")
        self.active_status = status_spinner
        try:
            with status_spinner:
                result = agent.run(goal)
        finally:
            self.active_status = None

        console.print()
        status = result.get("status")
        files = result.get("files_modified", [])
        summary = result.get("summary", "")

        if status == "completed":
            title = "[bold green]✓ ASTRA Solution[/bold green]" if not files else "[bold green]✓ ASTRA Task Completed[/bold green]"
            border = "green"
        elif status == "error":
            title = "[bold red]✗ ASTRA Task Failed[/bold red]"
            border = "red"
        else:
            title = f"[bold yellow]⏸ ASTRA: {status.upper()}[/bold yellow]"
            border = "yellow"

        if result.get("error"):
            console.print(Panel(f"[bold red]Error:[/bold red] {result['error']}", title=title, border_style=border, padding=(1, 2)))
        elif summary:
            if files:
                summary += "\n\n### 📝 Modified Files\n" + "\n".join(f"- `{f}`" for f in files)
            md = Markdown(summary, code_theme="monokai")
            console.print(
                Panel(
                    md,
                    title=title,
                    border_style=border,
                    padding=(1, 2),
                    subtitle=f"[dim]Iterations: {result.get('iterations', 0)}[/dim]",
                    subtitle_align="right",
                )
            )
        console.print()

    def run_repl(self) -> None:
        self.print_banner()

        while True:
            try:
                console.print("[bold cyan]astra[/bold cyan] [bold green]❯[/bold green] ", end="")
                user_input = input().strip()

                if not user_input:
                    continue

                if user_input in ("/exit", "/quit", "exit", "quit", ":q"):
                    console.print("[dim]✦ Exiting ASTRA. Bye![/dim]\n")
                    break

                if user_input.lower().strip() in ("hey", "hi", "hello", "yo", "sup", "hey astra", "hi astra", "hello astra"):
                    console.print(
                        Panel(
                            "👋 [bold green]Hey there![/bold green] I am ASTRA, powered by your fine-tuned Gemma model.\n"
                            "Give me any coding task, bug fix, or function to build!\n\n"
                            "[dim]Examples:\n"
                            "  • write a python script to reverse a string\n"
                            "  • create a fast binary search algorithm in python\n"
                            "  • /help to see all agent commands[/dim]",
                            title="[bold cyan]ASTRA Assistant[/bold cyan]",
                            border_style="cyan",
                            padding=(1, 2),
                        )
                    )
                    console.print()
                    continue

                if user_input in ("/help", "?", "help"):
                    self.show_help()
                    continue

                if user_input in ("/clear", "/cls", "clear", "cls"):
                    os.system("cls" if os.name == "nt" else "clear")
                    self.print_banner()
                    continue

                if user_input in ("/status", "/git", "git status"):
                    self.show_status()
                    continue

                if user_input in ("/diff", "git diff"):
                    self.show_diff()
                    continue

                if user_input.startswith("/files") or user_input.startswith("/ls"):
                    parts = user_input.split(maxsplit=1)
                    target = parts[1].strip() if len(parts) > 1 else "."
                    out = self.tools.list_dir(target)
                    console.print(Panel(out, title=f"Files in {target}", border_style="cyan"))
                    console.print()
                    continue

                if user_input.startswith("/search "):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1 and parts[1].strip():
                        q = parts[1].strip()
                        with console.status(f"[bold cyan]Searching web for '{q}'...[/bold cyan]", spinner="dots"):
                            res = self.tools.web_search(q)
                        console.print(Panel(Markdown(res), title=f"[bold cyan]🔍 Web Search: {q}[/bold cyan]", border_style="cyan", padding=(1, 2)))
                        console.print()
                    else:
                        console.print("[yellow]Usage: /search <query keywords>[/yellow]\n")
                    continue

                # Direct shell command auto-execution (git, pip, pytest, npm, docker, etc.)
                first_word = user_input.split()[0].lower() if user_input.split() else ""
                if first_word in ("git", "pip", "pytest", "npm", "docker", "cargo", "dir", "ls") and not any(w in user_input.lower() for w in ["write", "create", "how", "why", "what", "explain", "implement"]):
                    console.print(f"[bold cyan]$[/bold cyan] [bold]{user_input}[/bold]")
                    res = self.tools.run_command(user_input)
                    if res.strip():
                        console.print(res)
                    console.print()
                    continue

                if user_input.startswith("/run ") or user_input.startswith("!"):
                    cmd = user_input[5:] if user_input.startswith("/run ") else user_input[1:]
                    console.print(f"[bold cyan]$[/bold cyan] {cmd}")
                    res = self.tools.run_command(cmd)
                    console.print(res)
                    console.print()
                    continue

                if user_input.startswith("/model"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        self.model = parts[1].strip()
                        console.print(f"[green]✓ Switched model to:[/green] {get_model_badge(self.model)}\n")
                    else:
                        console.print(f"Active Model: {get_model_badge(self.model)}")
                        console.print("[dim]Usage: /model [groq | gemini | teja-gemma | ollama | claude | gpt-4o][/dim]\n")
                    continue

                if user_input.startswith("/repo"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        target = Path(parts[1].strip().strip('"\'')).resolve()
                        if not target.exists() or not target.is_dir():
                            console.print(f"[red]Error: Invalid directory '{target}'[/red]\n")
                            continue
                        self.workspace_path = target
                        self.tools = ToolExecutor(self.workspace_path)
                        console.print(f"[green]✓ Workspace switched to:[/green] [cyan]{self.workspace_path}[/cyan]\n")
                        self.print_banner()
                    else:
                        console.print(f"Active Workspace: [cyan]{self.workspace_path}[/cyan]\n")
                    continue

                if user_input in ("/ask", "/confirm", "/safety"):
                    self.ask_commands = not self.ask_commands
                    status_str = "[bold green]ON (will prompt before running commands)[/bold green]" if self.ask_commands else "[dim]OFF (auto-run commands)[/dim]"
                    console.print(f"🛡️ [bold cyan]Command Confirmation Guard:[/bold cyan] {status_str}\n")
                    continue

                # Run autonomous goal
                self.execute_goal(user_input)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Action cancelled. Type /exit to quit.[/dim]\n")
            except Exception as exc:
                console.print(f"[bold red]Error:[/bold red] {exc}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="ASTRA 3.0 Autonomous Agent CLI", add_help=False)
    parser.add_argument("goal", nargs="*", help="Direct goal to execute")
    parser.add_argument("--serve", action="store_true", help="Launch the ASTRA V4 API & WebSocket server for Desktop UI")
    parser.add_argument("--port", type=int, default=8765, help="Port for ASTRA API server (default: 8765)")
    parser.add_argument("--model", "-m", default=None, help="LLM model (e.g. gemini, ollama, teja-gemma)")
    parser.add_argument("--repo", "-r", default=None, help="Target workspace path")
    parser.add_argument("--ask", action="store_true", default=None, help="Prompt for approval before running shell commands (like Antigravity)")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-run commands without interactive approval prompts")
    parser.add_argument("--status", action="store_true", help="Show workspace git status")
    parser.add_argument("--diff", action="store_true", help="Show workspace git diff")
    parser.add_argument("--help", "-h", action="store_true", help="Show help information")

    args, unknown = parser.parse_known_args()

    if args.serve:
        from astra.server import run_server
        console.print(f"[bold cyan]🚀 Starting ASTRA V4 Runtime Server on http://127.0.0.1:{args.port}...[/bold cyan]")
        run_server(port=args.port)
        return

    # Determine ask_commands preference:
    # 1. If -y/--yes explicitly passed -> False
    # 2. If --ask explicitly passed -> True
    # 3. Otherwise default to True for interactive REPL or settings
    if args.yes:
        ask_pref = False
    elif args.ask:
        ask_pref = True
    else:
        # Default: True (Antigravity-style confirmation on commands)
        ask_pref = True

    cli = AstraCLI(workspace_path=args.repo, model=args.model, ask_commands=ask_pref)

    if args.help:
        cli.print_banner()
        cli.show_help()
        return

    if args.status:
        cli.show_status()
        return

    if args.diff:
        cli.show_diff()
        return

    combined = args.goal + unknown
    raw_goal = " ".join(combined).strip()
    if raw_goal:
        cli.execute_goal(raw_goal)
        return

    cli.run_repl()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
