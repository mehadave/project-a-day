import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from agent.difficulty import PROFILES

console = Console()
QUEUE_FILE = Path(__file__).parent.parent / "pending_project.json"


def collect_input_interactive() -> tuple[str, str]:
    console.print(Panel.fit(
        "[bold cyan]Project-a-Day Agent[/bold cyan]\n"
        "[dim]Powered by Claude Opus 4.6[/dim]",
        border_style="cyan",
    ))

    prompt_text = Prompt.ask("\n[bold]What would you like to build today?[/bold]")
    difficulty = Prompt.ask(
        "[bold]Difficulty level[/bold]",
        choices=["easy", "medium", "hard"],
        default="medium",
    )
    return prompt_text.strip(), difficulty


def queue_project() -> None:
    """Save a project idea to pending_project.json for the next scheduled run."""
    prompt_text, difficulty = collect_input_interactive()
    queue_data = {"prompt": prompt_text, "difficulty": difficulty}
    QUEUE_FILE.write_text(json.dumps(queue_data, indent=2))
    console.print(f"\n[green]Queued![/green] Project will be built at the next scheduled run.")
    console.print(f"[dim]Saved to: {QUEUE_FILE}[/dim]")


def collect_input(non_interactive: bool, auto_generate_fn=None) -> tuple[str, str]:
    """
    Return (prompt_text, difficulty_level).

    In headless mode: reads pending_project.json if present, otherwise calls
    auto_generate_fn() or exits.
    In interactive mode: prompts the user.
    """
    if non_interactive:
        if QUEUE_FILE.exists():
            data = json.loads(QUEUE_FILE.read_text())
            QUEUE_FILE.unlink()  # consume the queue file
            console.print(f"[green]Found queued project:[/green] {data['prompt']}")
            return data["prompt"], data.get("difficulty", "medium")
        elif auto_generate_fn is not None:
            return auto_generate_fn()
        else:
            console.print("[red]No queued project found. Run with --queue to set one.[/red]")
            sys.exit(1)
    else:
        return collect_input_interactive()
