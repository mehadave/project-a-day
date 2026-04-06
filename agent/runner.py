"""
Project builder using the Claude Agent SDK.

Claude Code runs in the project directory and writes files directly using
its built-in Write/Edit/Bash tools — no API key required, uses your Claude
Pro subscription via the installed `claude` CLI.
"""
import json
import re
from pathlib import Path

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from rich.console import Console

from agent.difficulty import DifficultyProfile

console = Console()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# More turns for harder projects (more files = more Write tool calls)
_MAX_TURNS = {"easy": 40, "medium": 80, "hard": 150}


async def _run_agent(prompt_text: str, difficulty: DifficultyProfile, project_dir: Path) -> None:
    """Async inner: run Claude Code agent inside project_dir."""
    system_prompt = (PROMPTS_DIR / "system_builder.txt").read_text()

    build_prompt = f"""\
Build a complete, working coding project based on this idea:

**Project idea:** {prompt_text}

**Difficulty:** {difficulty.level}
**Scope:** {difficulty.scope_description}
**Max files:** {difficulty.max_files}
**Include tests:** {difficulty.include_tests}
**Include CI config (.github/workflows/ci.yml):** {difficulty.include_ci}

Write all project files to the current directory. Make everything complete \
and working — no placeholders, no TODO stubs, no "coming soon" sections.

As the final step, create a file called `project_info.json` containing:
{{
  "project_name": "Human Readable Name",
  "slug": "kebab-case-slug",
  "description": "2-3 sentence description of what this project does.",
  "tech_stack": ["Python"]
}}
"""

    async for message in query(
        prompt=build_prompt,
        options=ClaudeAgentOptions(
            cwd=str(project_dir),
            allowed_tools=["Write", "Read", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",
            system_prompt=system_prompt,
            max_turns=_MAX_TURNS.get(difficulty.level, 80),
        ),
    ):
        # Print Claude's commentary so the user can follow along
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    # Truncate long lines to keep terminal tidy
                    text = block.text.strip()
                    if len(text) > 200:
                        text = text[:200] + "…"
                    console.print(f"[dim]{text}[/dim]")
        elif isinstance(message, ResultMessage) and message.result:
            console.print(f"\n[green]Agent finished:[/green] {message.result[:150]}")


def build_project_with_agent(
    prompt_text: str,
    difficulty: DifficultyProfile,
    base_dir: Path,
    date_str: str,
) -> tuple[Path, dict]:
    """
    Create the project directory, run Claude Code agent, return (project_path, info).

    info keys: project_name, slug, description, tech_stack, _slug (final dir name).
    """
    # Derive a safe temp slug from the prompt for the initial directory name
    temp_slug = re.sub(r"[^a-z0-9]+", "-", prompt_text.lower()).strip("-")[:40]
    project_dir = base_dir / f"{date_str}_{temp_slug}"
    project_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[dim]Working in: {project_dir}[/dim]\n")

    # Run the async agent synchronously
    anyio.run(_run_agent, prompt_text, difficulty, project_dir)

    # ---- Read project_info.json written by Claude ----
    info_path = project_dir / "project_info.json"
    info: dict = {}
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except Exception as exc:
            console.print(f"[yellow]Warning: could not parse project_info.json: {exc}[/yellow]")

    # Apply fallbacks in case Claude skipped the file or used wrong keys
    info.setdefault("project_name", prompt_text[:50].title())
    info.setdefault("slug", temp_slug)
    info.setdefault("description", f"Project built from prompt: {prompt_text}")
    info.setdefault("tech_stack", ["Unknown"])

    # ---- Rename directory to Claude's chosen slug ----
    proper_slug = re.sub(r"[^a-z0-9\-]", "", info["slug"].lower()).strip("-")[:50]
    final_slug = f"{date_str}_{proper_slug}"
    final_dir = base_dir / final_slug

    if project_dir.name != final_dir.name and not final_dir.exists():
        project_dir.rename(final_dir)
        project_dir = final_dir

    info["_slug"] = project_dir.name
    return project_dir, info
