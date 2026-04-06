import os
import subprocess
from pathlib import Path

import requests
from rich.console import Console

console = Console()


class GitHubClient:
    def __init__(self, token: str, username: str, repo_name: str, project_root: Path):
        self.token = token
        self.username = username
        self.repo_name = repo_name
        self.project_root = project_root
        self._api_base = "https://api.github.com"
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    # ------------------------------------------------------------------ #
    # Git helpers                                                           #
    # ------------------------------------------------------------------ #

    def _run(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        result = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            **kwargs,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed: {' '.join(cmd)}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        return result

    def ensure_git_init(self) -> None:
        """Initialize git repo if not already done."""
        if not (self.project_root / ".git").exists():
            self._run(["git", "init", "-b", "main"])
            self._run(["git", "config", "user.email", "projectaday@local"])
            self._run(["git", "config", "user.name", "Project-a-Day Agent"])
            console.print("[dim]Git repository initialized.[/dim]")

    def ensure_remote(self) -> None:
        """Add origin remote if not already set."""
        result = subprocess.run(
            ["git", "remote", "-v"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        if "origin" not in result.stdout:
            remote_url = f"https://github.com/{self.username}/{self.repo_name}.git"
            self._run(["git", "remote", "add", "origin", remote_url])
            console.print(f"[dim]Remote 'origin' set to {remote_url}[/dim]")

    # ------------------------------------------------------------------ #
    # GitHub API                                                            #
    # ------------------------------------------------------------------ #

    def ensure_repo_exists(self) -> None:
        """Create the GitHub repo if it doesn't exist yet."""
        resp = requests.get(
            f"{self._api_base}/repos/{self.username}/{self.repo_name}",
            headers=self._headers,
            timeout=15,
        )
        if resp.status_code == 404:
            console.print(f"[yellow]Creating GitHub repo:[/yellow] {self.repo_name}")
            create_resp = requests.post(
                f"{self._api_base}/user/repos",
                headers=self._headers,
                json={
                    "name": self.repo_name,
                    "description": "A project a day — built with Claude AI",
                    "private": False,
                    "auto_init": False,
                },
                timeout=15,
            )
            create_resp.raise_for_status()
            console.print(
                f"[green]Repo created:[/green] "
                f"https://github.com/{self.username}/{self.repo_name}"
            )
        elif resp.status_code == 200:
            console.print(
                f"[dim]Repo: https://github.com/{self.username}/{self.repo_name}[/dim]"
            )
        else:
            resp.raise_for_status()

    # ------------------------------------------------------------------ #
    # Commit & push                                                         #
    # ------------------------------------------------------------------ #

    def commit_and_push(
        self,
        project_slug: str,
        project_name: str,
        difficulty: str,
        prompt: str,
        tech_stack: list[str],
        n_files: int,
        date_str: str,
    ) -> None:
        """Stage the project folder, commit, and push to GitHub."""
        # Stage the new project folder
        self._run(["git", "add", f"projects/{project_slug}/"])

        # Also stage .gitkeep files on first run (silently ignores if already staged)
        subprocess.run(
            ["git", "add", "--ignore-unmatch", "projects/.gitkeep", "logs/.gitkeep"],
            cwd=self.project_root,
            capture_output=True,
        )

        # Check if there's anything to commit
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            console.print("[yellow]Nothing to commit — project already exists in git.[/yellow]")
            return

        # Build structured commit message
        prompt_preview = prompt[:80] + ("..." if len(prompt) > 80 else "")
        stack_str = ", ".join(tech_stack)
        commit_msg = (
            f"feat({date_str}): {project_name} [{difficulty}]\n\n"
            f"Generated by claude-opus-4-6\n"
            f'Prompt: "{prompt_preview}"\n'
            f"Stack: {stack_str}\n"
            f"Files: {n_files} files"
        )
        self._run(["git", "commit", "-m", commit_msg])

        # Push using token-embedded URL (never stored in .git/config)
        push_url = f"https://{self.token}@github.com/{self.username}/{self.repo_name}.git"
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        console.print("[dim]Pushing to GitHub...[/dim]")
        result = subprocess.run(
            ["git", "push", push_url, "main"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            # First push may need --set-upstream
            result2 = subprocess.run(
                ["git", "push", "--set-upstream", push_url, "main"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                env=env,
            )
            if result2.returncode != 0:
                raise RuntimeError(
                    f"Push failed:\nstdout: {result2.stdout}\nstderr: {result2.stderr}"
                )

        console.print(
            f"[green]Pushed![/green] "
            f"https://github.com/{self.username}/{self.repo_name}"
            f"/tree/main/projects/{project_slug}"
        )
