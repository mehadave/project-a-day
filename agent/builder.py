from pathlib import Path

import anthropic
from rich.console import Console

from agent.difficulty import DifficultyProfile
from agent.scaffolder import ProjectPlan

console = Console()
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def build_project(
    plan: ProjectPlan,
    difficulty: DifficultyProfile,
    client: anthropic.Anthropic,
) -> dict[str, str]:
    """
    Generate each file in the plan via a multi-turn conversation.
    Returns {file_path: file_content}.
    """
    system_prompt = (PROMPTS_DIR / "system_builder.txt").read_text()
    messages: list[dict] = []
    generated_files: dict[str, str] = {}

    for i, file_spec in enumerate(plan.files):
        console.print(
            f"\n[cyan]Generating file {i + 1}/{len(plan.files)}:[/cyan] "
            f"[bold]{file_spec.path}[/bold]"
        )
        console.print(f"[dim]{file_spec.description}[/dim]")

        # Build context summary of already-generated files
        context = ""
        if generated_files:
            context = "\n\nFiles already generated in this project:\n"
            for path, content in generated_files.items():
                # Include a preview so Claude can match imports/types
                preview = content[:500] + "\n[...truncated...]" if len(content) > 500 else content
                context += f"\n--- {path} ---\n{preview}\n"

        user_message = (
            f"Project: {plan.project_name}\n"
            f"Description: {plan.description}\n"
            f"Tech stack: {', '.join(plan.tech_stack)}\n"
            f"Difficulty: {difficulty.level}\n"
            f"{context}\n\n"
            f"Generate the complete contents of: {file_spec.path}\n"
            f"Purpose: {file_spec.description}\n\n"
            f"Output ONLY the raw file contents — no markdown fences, no explanation."
        )

        messages.append({"role": "user", "content": user_message})

        # Stream the file content
        file_content = ""
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=difficulty.max_tokens_per_file,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    print(event.delta.text, end="", flush=True)
                    file_content += event.delta.text

        print()  # newline after streaming

        # Append assistant turn to conversation history so next file has context
        messages.append({"role": "assistant", "content": file_content})
        generated_files[file_spec.path] = file_content

        line_count = len(file_content.splitlines())
        console.print(f"[green]✓[/green] {file_spec.path} ({line_count} lines)")

    return generated_files
