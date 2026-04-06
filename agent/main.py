#!/usr/bin/env python3
"""
Project-a-Day Agent — Main Orchestrator
Uses the Claude Agent SDK (Claude Pro subscription, no API key needed).
"""
import argparse
import os
import sys
import tomllib
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from agent.difficulty import PROFILES
from agent.github_client import GitHubClient
from agent.intake import collect_input, queue_project
from agent.runner import build_project_with_agent

console = Console()
ROOT = Path(__file__).parent.parent


# ------------------------------------------------------------------ #
# Config loading                                                        #
# ------------------------------------------------------------------ #

def _load_dotenv(env_path: Path) -> None:
    """Minimal .env loader — does not overwrite vars already in the environment."""
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> tuple[dict, str]:
    """Load .env + config.toml. Returns (config_dict, github_token)."""
    _load_dotenv(ROOT / ".env")

    config_path = ROOT / "config.toml"
    if not config_path.exists():
        console.print("[red]Error:[/red] config.toml not found. Run setup.sh first.")
        sys.exit(1)

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        console.print("[red]Error:[/red] GITHUB_TOKEN not set in .env")
        sys.exit(1)

    return config, github_token


# ------------------------------------------------------------------ #
# Main run                                                              #
# ------------------------------------------------------------------ #

def run(args: argparse.Namespace) -> None:
    config, github_token = load_config()

    github_cfg = config.get("github", {})
    agent_cfg = config.get("agent", {})
    projects_cfg = config.get("projects", {})

    username = github_cfg.get("username", "")
    repo_name = github_cfg.get("repo_name", "project-a-day")
    default_difficulty = agent_cfg.get("default_difficulty", "medium")

    if not username or username == "YOUR_GITHUB_USERNAME":
        console.print("[red]Error:[/red] Set your GitHub username in config.toml")
        sys.exit(1)

    base_dir_str = projects_cfg.get("base_dir", "")
    base_dir = Path(base_dir_str) if base_dir_str else ROOT / "projects"
    base_dir.mkdir(parents=True, exist_ok=True)

    # --queue mode: save idea for tomorrow and exit
    if args.queue:
        queue_project()
        return

    # Headless fallback: let Claude pick the idea itself
    def auto_gen() -> tuple[str, str]:
        console.print("[yellow]No queued project. Claude will choose the idea.[/yellow]")
        return (
            f"Come up with a creative and interesting {default_difficulty}-level "
            f"project idea and build it.",
            default_difficulty,
        )

    prompt_text, difficulty_str = collect_input(
        non_interactive=args.headless,
        auto_generate_fn=auto_gen if args.headless else None,
    )

    difficulty = PROFILES.get(difficulty_str, PROFILES["medium"])
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    console.print(Panel.fit(
        f"[bold]Idea:[/bold] {prompt_text}\n"
        f"[dim]Difficulty: {difficulty_str.upper()} | Date: {date_str}[/dim]",
        border_style="green",
        title="Project-a-Day",
    ))

    # ---- Build ----
    project_path, info = build_project_with_agent(prompt_text, difficulty, base_dir, date_str)

    # Count files (exclude project_info.json metadata)
    all_files = [
        f for f in project_path.rglob("*")
        if f.is_file() and f.name != "project_info.json"
    ]
    console.print(f"\n[green]Built {len(all_files)} files →[/green] {project_path}")

    # ---- GitHub ----
    github = GitHubClient(
        token=github_token,
        username=username,
        repo_name=repo_name,
        project_root=ROOT,
    )
    github.ensure_git_init()
    github.ensure_repo_exists()
    github.ensure_remote()
    github.commit_and_push(
        project_slug=info["_slug"],
        project_name=info.get("project_name", prompt_text[:50]),
        difficulty=difficulty_str,
        prompt=prompt_text,
        tech_stack=info.get("tech_stack", ["Unknown"]),
        n_files=len(all_files),
        date_str=date_str,
    )

    console.print(Panel.fit(
        f"[bold green]Done![/bold green]\n"
        f"[bold]{info.get('project_name', 'Project')}[/bold]\n"
        f"{info.get('description', '')}\n\n"
        f"Local:  {project_path}\n"
        f"GitHub: https://github.com/{username}/{repo_name}"
        f"/tree/main/projects/{info['_slug']}",
        border_style="green",
        title="Complete",
    ))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project-a-Day Agent — builds and commits a new project every day",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without interactive input (used by launchd daily trigger)",
    )
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Queue a project idea for tomorrow's scheduled 9 AM build",
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
