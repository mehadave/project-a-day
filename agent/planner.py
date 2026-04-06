import json
from pathlib import Path

import anthropic
from rich.console import Console

from agent.difficulty import DifficultyProfile
from agent.scaffolder import FileSpec, ProjectPlan

console = Console()
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def generate_plan(prompt: str, difficulty: DifficultyProfile, client: anthropic.Anthropic) -> ProjectPlan:
    """Call Claude to produce a JSON project plan, return a ProjectPlan dataclass."""
    system_prompt = (PROMPTS_DIR / "system_planner.txt").read_text()

    user_message = (
        f"Create a project plan for the following idea:\n\n"
        f"**Project idea:** {prompt}\n\n"
        f"**Difficulty level:** {difficulty.level}\n\n"
        f"**Scope constraints:**\n{difficulty.scope_description}\n\n"
        f"**Max files:** {difficulty.max_files}\n"
        f"**Include tests:** {difficulty.include_tests}\n"
        f"**Include CI config:** {difficulty.include_ci}\n\n"
        f"Output ONLY the JSON plan, nothing else."
    )

    console.print("[dim]Generating project plan...[/dim]")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=difficulty.max_tokens_plan,
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract text block (skip thinking blocks)
    text = next((b.text for b in response.content if b.type == "text"), "")

    # Strip accidental markdown fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(text)

    files = [FileSpec(path=f["path"], description=f["description"]) for f in data["files"]]
    return ProjectPlan(
        project_name=data["project_name"],
        slug=data["slug"],
        description=data["description"],
        tech_stack=data.get("tech_stack", ["Python"]),
        files=files,
    )


def auto_generate_prompt(difficulty_level: str, client: anthropic.Anthropic) -> tuple[str, str]:
    """Generate a random project idea for autonomous/headless mode."""
    console.print("[yellow]No queued project. Auto-generating idea...[/yellow]")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": (
                f"Suggest one creative and interesting coding project idea suitable for "
                f"a '{difficulty_level}' difficulty level. "
                f"Output ONLY the project idea in 1-2 sentences, nothing else."
            ),
        }],
    )
    idea = next((b.text for b in response.content if b.type == "text"), "").strip()
    console.print(f"[green]Auto-generated idea:[/green] {idea}")
    return idea, difficulty_level
