from dataclasses import dataclass


@dataclass
class DifficultyProfile:
    level: str
    max_files: int
    include_tests: bool
    include_docs: bool
    include_ci: bool
    max_tokens_plan: int
    max_tokens_per_file: int
    scope_description: str


PROFILES: dict[str, DifficultyProfile] = {
    "easy": DifficultyProfile(
        level="easy",
        max_files=4,
        include_tests=False,
        include_docs=True,
        include_ci=False,
        max_tokens_plan=8000,
        max_tokens_per_file=4000,
        scope_description=(
            "Build a minimal, working single-purpose project. "
            "3-4 files maximum including README. No tests needed. "
            "Focus on clarity and correctness over completeness. "
            "Pick the single best language (Python, JavaScript, or TypeScript). "
            "Examples: password generator, file renamer, ASCII art generator, "
            "simple calculator, text stats counter, coin flip simulator."
        ),
    ),
    "medium": DifficultyProfile(
        level="medium",
        max_files=8,
        include_tests=True,
        include_docs=True,
        include_ci=False,
        max_tokens_plan=8000,
        max_tokens_per_file=6000,
        scope_description=(
            "Build a well-structured project with separate modules. "
            "6-8 files maximum. Include 1 test file and package/dependency file. "
            "Use sensible abstractions but avoid over-engineering. "
            "Pick the best language (Python, JavaScript, or TypeScript). "
            "Examples: weather dashboard CLI, expense tracker with file persistence, "
            "Markdown-to-HTML converter, URL shortener, REST API client."
        ),
    ),
    "hard": DifficultyProfile(
        level="hard",
        max_files=16,
        include_tests=True,
        include_docs=True,
        include_ci=True,
        max_tokens_plan=8000,
        max_tokens_per_file=8000,
        scope_description=(
            "Build a production-quality project with proper packaging, "
            "comprehensive tests, CI config, and full documentation. "
            "10-16 files maximum. Use a proper project structure (src/ layout for Python, "
            "src/ for TypeScript). Include .github/workflows/ci.yml. "
            "Pick the best language (Python, JavaScript, or TypeScript). "
            "Examples: FastAPI REST API with persistence, Discord bot with commands, "
            "web scraper with scheduling, terminal note-taking app with search."
        ),
    ),
}
