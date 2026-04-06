from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileSpec:
    path: str
    description: str


@dataclass
class ProjectPlan:
    project_name: str
    slug: str
    description: str
    tech_stack: list[str]
    files: list[FileSpec] = field(default_factory=list)


def write_project(date_slug: str, plan: ProjectPlan, files: dict[str, str], base_dir: Path) -> Path:
    """Write all generated files to disk under base_dir/date_slug/."""
    project_dir = base_dir / date_slug
    project_dir.mkdir(parents=True, exist_ok=True)

    for file_path, content in files.items():
        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    return project_dir
